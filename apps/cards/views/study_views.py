from typing import Any
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView
from django.http import HttpResponse
from apps.cards.models import Deck, Flashcard, UserCardProgress
from apps.cards.services.srs_engine import SRSEngine
from apps.cards.services.llm_generator import LLMGeneratorService


def is_card_mastered(progress: UserCardProgress) -> bool:
    """
    Критерий освоенности карточки.
    SQL: sql/queries.sql, строка 44 (easiness_factor >= 1.5 AND consecutive_correct >= 1)
    """
    return progress.easiness_factor >= 1.5 and progress.consecutive_correct >= 1


class StudySessionView(LoginRequiredMixin, TemplateView):
    """
    Учебная сессия.
    SQL: sql/queries.sql, строки 18-24 (get_due_cards)
    SQL: sql/queries.sql, строки 26-36 (process_review - UPDATE)
    """
    template_name = 'cards/study_session.html'

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        if not (deck.owner == request.user or request.user.is_staff or deck.visibility == 'public'):
            return redirect('cards:deck_list')
        session_key = f'study_session_{deck.pk}_completed'
        if session_key not in request.session:
            request.session[session_key] = []
            SRSEngine.reset_all_progress(request.user, deck)
            SRSEngine.initialize_deck_progress(request.user, deck)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        user = self.request.user
        due_cards = SRSEngine.get_due_cards(user, deck)
        stats = SRSEngine.get_statistics(user, deck)
        session_key = f'study_session_{deck.pk}_completed'
        completed_ids = self.request.session.get(session_key, [])
        current_card = next((c for c in due_cards if c.pk not in completed_ids), None)
        if current_card is None:
            context.update({'deck': deck, 'stats': stats, 'session_completed': True, 'no_cards': True})
            return context
        progress = UserCardProgress.objects.get(user=user, flashcard=current_card)
        all_cards = list(deck.flashcard_set.filter(is_active=True))
        llm_service = LLMGeneratorService()
        exercise = llm_service.generate_exercise(card=current_card, exercise_type="multiple_choice", all_cards=all_cards)
        remaining_count = sum(1 for c in due_cards if c.pk not in completed_ids)
        context.update({'deck': deck, 'card': current_card, 'progress': progress, 'total_due': remaining_count, 'stats': stats, 'exercise': exercise, 'session_completed': False, 'no_cards': False})
        return context

    def post(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        card_id = request.POST.get('card_id', '').strip()
        if not card_id:
            return redirect('cards:study_session', deck_pk=deck.pk)
        try:
            card_id_int = int(card_id)
        except ValueError:
            return redirect('cards:study_session', deck_pk=deck.pk)
        is_correct = request.POST.get('is_correct') == 'true'
        card = get_object_or_404(Flashcard, pk=card_id_int, deck=deck)
        progress = UserCardProgress.objects.get(user=request.user, flashcard=card)
        quality = 5 if is_correct else 2
        SRSEngine.process_review(progress, quality)
        session_key = f'study_session_{deck.pk}_completed'
        completed_ids = request.session.get(session_key, [])
        if card_id_int not in completed_ids:
            completed_ids.append(card_id_int)
            request.session[session_key] = completed_ids
        due_cards = SRSEngine.get_due_cards(request.user, deck)
        remaining = [c for c in due_cards if c.pk not in completed_ids]
        if remaining:
            return redirect('cards:study_session', deck_pk=deck.pk)
        request.session.pop(session_key, None)
        return redirect('cards:study_results', deck_pk=deck.pk)


class StudyResultsView(LoginRequiredMixin, TemplateView):
    """Результаты обучения."""
    template_name = 'cards/study_results.html'

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        if not (deck.owner == request.user or request.user.is_staff or deck.visibility == 'public'):
            return redirect('cards:deck_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        user = self.request.user
        stats = SRSEngine.get_statistics(user, deck)
        all_progress = UserCardProgress.objects.filter(user=user, flashcard__deck=deck, flashcard__is_active=True).select_related('flashcard')
        mastered_cards = []
        struggling_cards = []
        for progress in all_progress:
            card_info = {'id': progress.flashcard.pk, 'term': progress.flashcard.term, 'definition': progress.flashcard.definition, 'easiness_factor': round(progress.easiness_factor, 2), 'consecutive_correct': progress.consecutive_correct, 'total_errors': progress.total_errors}
            if is_card_mastered(progress):
                mastered_cards.append(card_info)
            else:
                struggling_cards.append(card_info)
        struggling_cards.sort(key=lambda x: x['easiness_factor'])
        context.update({'deck': deck, 'stats': stats, 'mastered_cards': mastered_cards, 'struggling_cards': struggling_cards, 'mastered_count': len(mastered_cards), 'struggling_count': len(struggling_cards), 'total_cards': len(mastered_cards) + len(struggling_cards)})
        return context


class RetryStrugglingView(LoginRequiredMixin, TemplateView):
    """Повторение проблемных карточек."""
    template_name = 'cards/study_session.html'

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        if not (deck.owner == request.user or request.user.is_staff or deck.visibility == 'public'):
            return redirect('cards:deck_list')
        session_key = f'retry_session_{deck.pk}_completed'
        if session_key not in request.session:
            request.session[session_key] = []
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        user = self.request.user
        all_progress = UserCardProgress.objects.filter(user=user, flashcard__deck=deck, flashcard__is_active=True).select_related('flashcard')
        struggling_cards = [p.flashcard for p in all_progress if not is_card_mastered(p)]
        if not struggling_cards:
            return redirect('cards:retry_complete', deck_pk=deck.pk)
        session_key = f'retry_session_{deck.pk}_completed'
        completed_ids = self.request.session.get(session_key, [])
        current_card = next((c for c in struggling_cards if c.pk not in completed_ids), None)
        if current_card is None:
            self.request.session[session_key] = []
            current_card = struggling_cards[0]
        progress = UserCardProgress.objects.get(user=user, flashcard=current_card)
        stats = SRSEngine.get_statistics(user, deck)
        all_cards = list(deck.flashcard_set.filter(is_active=True))
        llm_service = LLMGeneratorService()
        exercise = llm_service.generate_exercise(card=current_card, exercise_type="auto", all_cards=all_cards)
        remaining_in_round = len([c for c in struggling_cards if c.pk not in completed_ids]) or len(struggling_cards)
        context.update({'deck': deck, 'card': current_card, 'progress': progress, 'total_due': remaining_in_round, 'stats': stats, 'exercise': exercise, 'session_completed': False, 'is_retry_mode': True})
        return context

    def post(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        card_id = request.POST.get('card_id', '').strip()
        if not card_id:
            return redirect('cards:retry_struggling', deck_pk=deck.pk)
        try:
            card_id_int = int(card_id)
        except ValueError:
            return redirect('cards:retry_struggling', deck_pk=deck.pk)
        is_correct = request.POST.get('is_correct') == 'true'
        card = get_object_or_404(Flashcard, pk=card_id_int, deck=deck)
        progress = UserCardProgress.objects.get(user=request.user, flashcard=card)
        SRSEngine.process_review(progress, 5 if is_correct else 2)
        session_key = f'retry_session_{deck.pk}_completed'
        completed_ids = request.session.get(session_key, [])
        if card_id_int not in completed_ids:
            completed_ids.append(card_id_int)
            request.session[session_key] = completed_ids
        all_progress = UserCardProgress.objects.filter(user=request.user, flashcard__deck=deck, flashcard__is_active=True)
        struggling_cards = [p.flashcard for p in all_progress if not is_card_mastered(p)]
        if not struggling_cards:
            request.session.pop(session_key, None)
            return redirect('cards:retry_complete', deck_pk=deck.pk)
        struggling_ids = [c.pk for c in struggling_cards]
        if all(cid in completed_ids for cid in struggling_ids):
            return redirect('cards:retry_results', deck_pk=deck.pk)
        return redirect('cards:retry_struggling', deck_pk=deck.pk)


class RetryResultsView(LoginRequiredMixin, TemplateView):
    """Промежуточные результаты."""
    template_name = 'cards/retry_results.html'

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        if not (deck.owner == request.user or request.user.is_staff or deck.visibility == 'public'):
            return redirect('cards:deck_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        user = self.request.user
        stats = SRSEngine.get_statistics(user, deck)
        all_progress = UserCardProgress.objects.filter(user=user, flashcard__deck=deck, flashcard__is_active=True).select_related('flashcard')
        mastered_cards = []
        struggling_cards = []
        for progress in all_progress:
            card_info = {'id': progress.flashcard.pk, 'term': progress.flashcard.term, 'definition': progress.flashcard.definition, 'easiness_factor': round(progress.easiness_factor, 2), 'consecutive_correct': progress.consecutive_correct, 'total_errors': progress.total_errors}
            if is_card_mastered(progress):
                mastered_cards.append(card_info)
            else:
                struggling_cards.append(card_info)
        context.update({'deck': deck, 'stats': stats, 'mastered_cards': mastered_cards, 'struggling_cards': struggling_cards, 'mastered_count': len(mastered_cards), 'struggling_count': len(struggling_cards), 'total_cards': len(mastered_cards) + len(struggling_cards), 'is_retry_results': True})
        return context


class RetryCompleteView(LoginRequiredMixin, TemplateView):
    """Все карточки освоены."""
    template_name = 'cards/retry_complete.html'

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        if not (deck.owner == request.user or request.user.is_staff or deck.visibility == 'public'):
            return redirect('cards:deck_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        user = self.request.user
        SRSEngine._update_deck_progress(user, deck)
        stats = SRSEngine.get_statistics(user, deck)
        context.update({'deck': deck, 'stats': stats})
        return context