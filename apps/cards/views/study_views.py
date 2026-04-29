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

        if request.method == 'GET' and self.session_key_stage not in request.session:
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
                # Сохраняем ВСЕ карточки: те, что в struggling — неверные, остальные — верные
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
                for key in [self.session_key_stage, self.session_key_completed,
                           self.session_key_due_total, self.session_key_test_pending,
                           self.session_key_struggling]:
                    self.request.session.pop(key, None)
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
        
        session_key = f'retry_session_{deck.pk}_completed'
        if session_key not in request.session:
            request.session[session_key] = []
            all_progress = UserCardProgress.objects.filter(
                user=request.user,
                flashcard__deck=deck,
                flashcard__is_active=True
            )
            struggling = [p.flashcard for p in all_progress if not is_card_mastered(p)]
            request.session[f'retry_session_{deck.pk}_total'] = len(struggling)
        
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs["deck_pk"])
        user = self.request.user

        all_progress = UserCardProgress.objects.filter(
            user=user, flashcard__deck=deck, flashcard__is_active=True
        ).select_related("flashcard")

        struggling_cards = []
        for p in all_progress:
            if not is_card_mastered(p):
                struggling_cards.append(p.flashcard)

        if not struggling_cards:
            return redirect("cards:retry_complete", deck_pk=deck.pk)

        session_key = f"retry_session_{deck.pk}_completed"
        completed_ids = self.request.session.get(session_key, [])

        current_card = None
        for card in struggling_cards:
            if card.pk not in completed_ids:
                current_card = card
                break

        if current_card is None:
            self.request.session[session_key] = []
            current_card = struggling_cards[0]

        progress = UserCardProgress.objects.get(user=user, flashcard=current_card)
        stats = SRSEngine.get_statistics(user, deck)
        all_cards = list(deck.flashcard_set.filter(is_active=True))

        llm_service = LLMGeneratorService()
        exercise = llm_service.generate_exercise(
            card=current_card, exercise_type="auto", all_cards=all_cards
        )

        total_in_round = self.request.session.get(f'retry_session_{deck.pk}_total', len(struggling_cards))
        answered_in_round = len(completed_ids)
        current_number = answered_in_round + 1

        context.update({
            "deck": deck,
            "card": current_card,
            "progress": progress,
            "total_due": total_in_round,
            "current_number": current_number,
            "stats": stats,
            "exercise": exercise,
            "session_completed": False,
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

        card = get_object_or_404(Flashcard, pk=card_id_int, deck=deck)
        progress = UserCardProgress.objects.get(user=request.user, flashcard=card)

        quality = 5 if is_correct else 2
        SRSEngine.process_review(progress, quality)

        session_key = f"retry_session_{deck.pk}_completed"
        completed_ids = request.session.get(session_key, [])

        if card_id_int not in completed_ids:
            completed_ids.append(card_id_int)
            request.session[session_key] = completed_ids

        all_progress = UserCardProgress.objects.filter(
            user=request.user, flashcard__deck=deck, flashcard__is_active=True
        )

        struggling_cards = []
        for p in all_progress:
            if not is_card_mastered(p):
                struggling_cards.append(p.flashcard)

        if not struggling_cards:
            request.session.pop(session_key, None)
            return redirect("cards:retry_complete", deck_pk=deck.pk)

        struggling_ids = [c.pk for c in struggling_cards]
        all_completed_in_round = all(cid in completed_ids for cid in struggling_ids)

        if all_completed_in_round:
            return redirect("cards:retry_results", deck_pk=deck.pk)

        return redirect("cards:retry_struggling", deck_pk=deck.pk)




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