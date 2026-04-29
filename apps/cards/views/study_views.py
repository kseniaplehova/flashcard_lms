from django.utils import timezone
from datetime import timedelta
from typing import Any
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView
from django.http import HttpResponse
from apps.cards.models import Deck, Flashcard, UserCardProgress
from apps.cards.services.srs_engine import SRSEngine
from apps.cards.services.llm_generator import LLMGeneratorService



def is_card_mastered(progress: UserCardProgress) -> bool:
    return progress.easiness_factor >= 1.5 and progress.consecutive_correct >= 1


class StudySessionView(LoginRequiredMixin, TemplateView):
    template_name = "cards/study_session.html"

    def dispatch(self, request, *args, **kwargs):
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])

        if not (deck.owner == request.user or request.user.is_staff or deck.visibility == 'public'):
            return redirect("cards:deck_list")

        self.session_key_completed = f"study_session_{deck.pk}_completed"
        self.session_key_struggling = f"study_session_{deck.pk}_struggling"
        self.session_key_stage = f"study_session_{deck.pk}_stage"
        self.session_key_due_total = f"study_session_{deck.pk}_due_total"
        self.session_key_test_pending = f"study_session_{deck.pk}_test_pending"
        self.session_key_test_results = f"study_session_{deck.pk}_test_results"
                # Если сессия завершена и есть результаты — редирект на results
        self.session_key_all_done = f"study_session_{deck.pk}_all_done"
        if request.method == 'GET' and request.session.get(self.session_key_all_done):
            for key in [self.session_key_stage, self.session_key_completed,
                       self.session_key_due_total, self.session_key_test_pending,
                       self.session_key_struggling, self.session_key_all_done]:
                request.session.pop(key, None)
            return redirect('cards:study_results', deck_pk=deck.pk)

        if request.method == 'GET' and self.session_key_stage not in request.session:
            user = request.user
            today = timezone.now().date()
            if user.last_activity_date != today:
                yesterday = today - timedelta(days=1)
                if user.last_activity_date == yesterday:
                    user.current_streak += 1
                else:
                    user.current_streak = 1
                user.last_activity_date = today
                user.save(update_fields=['current_streak', 'last_activity_date'])
            
            all_cards = Flashcard.objects.filter(deck=deck, is_active=True)
            total_count = all_cards.count()

            request.session[self.session_key_stage] = 'flashcard'
            request.session[self.session_key_completed] = []
            request.session[self.session_key_struggling] = []
            request.session[self.session_key_due_total] = total_count
            request.session[self.session_key_test_pending] = []
            request.session[self.session_key_test_results] = {}

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        user = self.request.user

        stage = self.request.session.get(self.session_key_stage, 'flashcard')
        completed = self.request.session.get(self.session_key_completed, [])
        struggling = self.request.session.get(self.session_key_struggling, [])
        total_due = self.request.session.get(self.session_key_due_total, 0)

        all_active_cards = list(Flashcard.objects.filter(deck=deck, is_active=True))

        if stage == 'flashcard':
            available = [c for c in all_active_cards if c.pk not in completed]

            if not available:
                if struggling:
                    self.request.session[self.session_key_stage] = 'test'
                    self.request.session[self.session_key_test_pending] = struggling.copy()
                    self.request.session[self.session_key_completed] = []
                    self.request.session.modified = True
                    return self.get_context_data(**kwargs)
                else:
                    # Нет "не знаю" — все карточки освоены
                    results = {}
                    for c in all_active_cards:
                        results[str(c.pk)] = {
                            'term': c.term,
                            'definition': c.definition,
                            'correct': True
                        }
                    self.request.session[self.session_key_test_results] = results
                    for key in [self.session_key_stage, self.session_key_completed,
                               self.session_key_due_total, self.session_key_test_pending,
                               self.session_key_struggling]:
                        self.request.session.pop(key, None)
                    self.request.session.modified = True
                    context.update({"deck": deck, "no_cards": True})
                    return context

            card = available[0]
            context.update({
                "deck": deck,
                "card": card,
                "stage": "flashcard",
                "total_due": total_due,
                "current_number": len(completed) + 1,
                "exercise": self.llm_service.generate_exercise(card, "flashcard"),
            })
        else:
            pending_ids = self.request.session.get(self.session_key_test_pending, [])
            completed_test = self.request.session.get(self.session_key_completed, [])
            remaining = [pid for pid in pending_ids if pid not in completed_test]

            if not remaining:
                results = {}
                struggling_set = set(struggling)
                for c in all_active_cards:
                    is_correct = c.pk not in struggling_set
                    results[str(c.pk)] = {
                        'term': c.term,
                        'definition': c.definition,
                        'correct': is_correct
                    }
                self.request.session[self.session_key_test_results] = results
                self.request.session[self.session_key_all_done] = True
                self.request.session.modified = True
                context.update({"deck": deck, "no_cards": True})
                return context

            next_id = remaining[0]
            card = get_object_or_404(Flashcard, pk=next_id, deck=deck)
            context.update({
                "deck": deck,
                "card": card,
                "stage": "test",
                "total_due": len(pending_ids),
                "current_number": len(completed_test) + 1,
                "exercise": self.llm_service.generate_exercise(card, "auto", all_active_cards),
            })
        return context

    def post(self, request, *args, **kwargs):
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])

        card_id = request.POST.get('card_id')
        if not card_id:
            return redirect('cards:study_session', deck_pk=deck.pk)

        try:
            card_id = int(card_id)
        except ValueError:
            return redirect('cards:study_session', deck_pk=deck.pk)

        is_correct = request.POST.get('is_correct') == 'true'

        completed = request.session.get(self.session_key_completed, [])

        if card_id not in completed:
            completed.append(card_id)
            request.session[self.session_key_completed] = completed

            stage = request.session.get(self.session_key_stage, 'flashcard')
            if stage == 'flashcard' and not is_correct:
                struggling = request.session.get(self.session_key_struggling, [])
                if card_id not in struggling:
                    struggling.append(card_id)
                    request.session[self.session_key_struggling] = struggling

            request.session.modified = True

        return redirect('cards:study_session', deck_pk=deck.pk)

    @property
    def llm_service(self):
        if not hasattr(self, '_llm'):
            self._llm = LLMGeneratorService()
        return self._llm


class StudyResultsView(LoginRequiredMixin, TemplateView):
    template_name = "cards/study_results.html"

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs["deck_pk"])
        if not (deck.owner == request.user or request.user.is_staff or deck.visibility == "public"):
            return redirect("cards:deck_list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs["deck_pk"])
        
        results_key = f"study_session_{deck.pk}_test_results"
        results = self.request.session.get(results_key, {})
        
        all_cards = Flashcard.objects.filter(deck=deck, is_active=True)
        total = all_cards.count()
        
        mastered = [r for r in results.values() if r.get('correct')]
        struggling = [r for r in results.values() if not r.get('correct')]
        mastered_percent = int((len(mastered) / total) * 100) if total > 0 else 0
        
        context.update({
            "deck": deck,
            "total_cards": total,
            "mastered_cards": mastered,
            "struggling_cards": struggling,
            "mastered_count": len(mastered),
            "struggling_count": len(struggling),
            "mastered_percent": mastered_percent,
        })
        return context


class RetryStrugglingView(LoginRequiredMixin, TemplateView):
    template_name = "cards/study_session.html"

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        if not (deck.owner == request.user or request.user.is_staff or deck.visibility == 'public'):
            return redirect('cards:deck_list')
        
        self.session_key_completed = f"retry_session_{deck.pk}_completed"
        self.session_key_total = f"retry_session_{deck.pk}_total"
        self.session_key_retry_results = f"retry_session_{deck.pk}_retry_results"
        
        if request.method == 'GET' and self.session_key_completed not in request.session:
            results_key = f"study_session_{deck.pk}_test_results"
            results = request.session.get(results_key, {})
            struggling_ids = [int(k) for k, v in results.items() if not v.get('correct')]
            
            if not struggling_ids:
                return redirect('cards:retry_results', deck_pk=deck.pk)
            
            request.session[self.session_key_completed] = []
            request.session[self.session_key_total] = len(struggling_ids)
            request.session[self.session_key_retry_results] = {}
        
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs["deck_pk"])
        user = self.request.user

        results_key = f"study_session_{deck.pk}_test_results"
        results = self.request.session.get(results_key, {})
        struggling_ids = [int(k) for k, v in results.items() if not v.get('correct')]
        
        completed = self.request.session.get(self.session_key_completed, [])
        total = self.request.session.get(self.session_key_total, len(struggling_ids))
        
        remaining = [pid for pid in struggling_ids if pid not in completed]
        
        if not remaining:
            # Сохраняем результаты ретрая
            retry_results = self.request.session.get(self.session_key_retry_results, {})
            all_cards = Flashcard.objects.filter(deck=deck, is_active=True)
            
            final_results = {}
            for c in all_cards:
                cid = str(c.pk)
                if cid in results:
                    if cid in retry_results:
                        final_results[cid] = retry_results[cid]
                    else:
                        final_results[cid] = results[cid]
                else:
                    final_results[cid] = results.get(cid, {'term': c.term, 'definition': c.definition, 'correct': True})
            
            self.request.session[results_key] = final_results
            for key in [self.session_key_completed, self.session_key_total, self.session_key_retry_results]:
                self.request.session.pop(key, None)
            
            # Возвращаем контекст с флагом для редиректа
            context.update({"deck": deck, "no_cards": True})
            return context

        card = get_object_or_404(Flashcard, pk=remaining[0], deck=deck)
        all_cards = list(Flashcard.objects.filter(deck=deck, is_active=True))

        context.update({
            "deck": deck,
            "card": card,
            "stage": "retry",
            "total_due": total,
            "current_number": len(completed) + 1,
            "exercise": LLMGeneratorService().generate_exercise(card, "auto", all_cards),
            "is_retry_mode": True,
        })
        return context

    def post(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs["deck_pk"])
        card_id = request.POST.get("card_id", "").strip()

        if not card_id:
            return redirect("cards:retry_struggling", deck_pk=deck.pk)

        try:
            card_id_int = int(card_id)
        except ValueError:
            return redirect("cards:retry_struggling", deck_pk=deck.pk)

        is_correct = request.POST.get("is_correct") == "true"
        
        retry_results = request.session.get(self.session_key_retry_results, {})
        card = get_object_or_404(Flashcard, pk=card_id_int, deck=deck)
        retry_results[str(card_id_int)] = {
            'term': card.term,
            'definition': card.definition,
            'correct': is_correct
        }
        request.session[self.session_key_retry_results] = retry_results

        completed = request.session.get(self.session_key_completed, [])
        if card_id_int not in completed:
            completed.append(card_id_int)
            request.session[self.session_key_completed] = completed
            request.session.modified = True

        return redirect('cards:retry_struggling', deck_pk=deck.pk)




class RetryCompleteView(LoginRequiredMixin, TemplateView):
    template_name = "cards/retry_complete.html"

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs["deck_pk"])
        if not (deck.owner == request.user or request.user.is_staff or deck.visibility == "public"):
            return redirect("cards:deck_list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs["deck_pk"])
        user = self.request.user

        SRSEngine._update_deck_progress(user, deck)
        stats = SRSEngine.get_statistics(user, deck)
        context.update({"deck": deck, "stats": stats})
        return context

class RetryResultsView(LoginRequiredMixin, TemplateView):
    template_name = "cards/retry_results.html"

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs["deck_pk"])
        if not (deck.owner == request.user or request.user.is_staff or deck.visibility == "public"):
            return redirect("cards:deck_list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs["deck_pk"])
        
        results_key = f"study_session_{deck.pk}_test_results"
        results = self.request.session.get(results_key, {})
        
        all_cards = Flashcard.objects.filter(deck=deck, is_active=True)
        total = all_cards.count()
        
        mastered = [r for r in results.values() if r.get('correct')]
        struggling = [r for r in results.values() if not r.get('correct')]
        mastered_percent = int((len(mastered) / total) * 100) if total > 0 else 0
        
        context.update({
            "deck": deck,
            "total_cards": total,
            "mastered_cards": mastered,
            "struggling_cards": struggling,
            "mastered_count": len(mastered),
            "struggling_count": len(struggling),
            "mastered_percent": mastered_percent,
        })
        return context