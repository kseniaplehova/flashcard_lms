from typing import Any
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView
from django.http import HttpResponse
from apps.cards.models import Deck, Flashcard, UserCardProgress
from apps.cards.services.srs_engine import SRSEngine
from apps.cards.services.llm_generator import LLMGeneratorService


# Критерий освоенности карточки
def is_card_mastered(progress: UserCardProgress) -> bool:
    """Карточка считается освоенной, если EF >= 2.0 и был хотя бы 1 правильный ответ."""
    return progress.easiness_factor >= 2.0 and progress.consecutive_correct >= 1


class StudySessionView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Учебная сессия с разными типами упражнений.
    """
    template_name = 'cards/study_session.html'
    
    def test_func(self) -> bool:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        return deck.owner == self.request.user  # type: ignore[attr-defined]
    
    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        session_key = f'study_session_{deck.pk}_completed'
        
        if session_key not in request.session:
            request.session[session_key] = []
            SRSEngine.reset_all_progress(request.user, deck)
            SRSEngine.initialize_deck_progress(request.user, deck)
            print("DEBUG: NEW SESSION STARTED - progress reset")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        user = self.request.user
        
        due_cards = SRSEngine.get_due_cards(user, deck)
        stats = SRSEngine.get_statistics(user, deck)
        
        session_key = f'study_session_{deck.pk}_completed'
        completed_ids = self.request.session.get(session_key, [])
        
        current_card = None
        for card in due_cards:
            if card.pk not in completed_ids:
                current_card = card
                break
        
        if current_card is None:
            context.update({
                'deck': deck,
                'stats': stats,
                'session_completed': True,
                'no_cards': True,
            })
            return context
        
        progress = UserCardProgress.objects.get(user=user, flashcard=current_card)
        all_cards = list(deck.flashcard_set.filter(is_active=True))  # type: ignore[attr-defined]
        
        llm_service = LLMGeneratorService()
        exercise = llm_service.generate_exercise(
            card=current_card,
            exercise_type="multiple_choice",
            all_cards=all_cards
        )
        
        remaining_count = sum(1 for c in due_cards if c.pk not in completed_ids)
        
        context.update({
            'deck': deck,
            'card': current_card,
            'progress': progress,
            'total_due': remaining_count,
            'stats': stats,
            'exercise': exercise,
            'session_completed': False,
            'no_cards': False,
        })
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


class StudyResultsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Страница с результатами обучения.
    """
    template_name = 'cards/study_results.html'
    
    def test_func(self) -> bool:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        return deck.owner == self.request.user  # type: ignore[attr-defined]
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        user = self.request.user
        
        stats = SRSEngine.get_statistics(user, deck)
        
        all_progress = UserCardProgress.objects.filter(
            user=user,
            flashcard__deck=deck,
            flashcard__is_active=True
        ).select_related('flashcard')
        
        mastered_cards = []
        struggling_cards = []
        
        print("=== DEBUG StudyResultsView ===")
        for progress in all_progress:
            card_info = {
                'id': progress.flashcard.pk,
                'term': progress.flashcard.term,
                'definition': progress.flashcard.definition,
                'easiness_factor': round(progress.easiness_factor, 2),
                'consecutive_correct': progress.consecutive_correct,
                'total_errors': progress.total_errors,
            }
            
            # ВАЖНО: проверяем условие
            is_mastered = is_card_mastered(progress)
            print(f"Card: {progress.flashcard.term}, EF={progress.easiness_factor:.2f}, correct={progress.consecutive_correct}, mastered={is_mastered}")
            
            if is_mastered:
                mastered_cards.append(card_info)
            else:
                struggling_cards.append(card_info)
        
        print(f"Mastered: {len(mastered_cards)}, Struggling: {len(struggling_cards)}")
        print("================================")
        
        struggling_cards.sort(key=lambda x: x['easiness_factor'])
        
        context.update({
            'deck': deck,
            'stats': stats,
            'mastered_cards': mastered_cards,
            'struggling_cards': struggling_cards,
            'mastered_count': len(mastered_cards),
            'struggling_count': len(struggling_cards),
            'total_cards': len(mastered_cards) + len(struggling_cards),
        })
        return context


class RetryStrugglingView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Повторение только проблемных карточек с зацикливанием.
    """
    template_name = 'cards/study_session.html'
    
    def test_func(self) -> bool:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        return deck.owner == self.request.user  # type: ignore[attr-defined]
    
    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        session_key = f'retry_session_{deck.pk}_completed'
        
        # Инициализируем сессию при первом заходе
        if session_key not in request.session:
            request.session[session_key] = []
            print("DEBUG: NEW RETRY SESSION STARTED")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        user = self.request.user
        
        # Получаем ВСЕ карточки и фильтруем проблемные
        all_progress = UserCardProgress.objects.filter(
            user=user,
            flashcard__deck=deck,
            flashcard__is_active=True
        ).select_related('flashcard')
        
        struggling_cards = []
        for p in all_progress:
            if not is_card_mastered(p):
                struggling_cards.append(p.flashcard)
        
        # Если проблемных карточек нет — показываем сообщение
        if not struggling_cards:
            stats = SRSEngine.get_statistics(user, deck)
            context.update({
                'deck': deck,
                'stats': stats,
                'no_cards': True,
                'all_mastered': True,
                'session_completed': True,
            })
            return context
        
        session_key = f'retry_session_{deck.pk}_completed'
        completed_ids = self.request.session.get(session_key, [])
        
        # Находим первую НЕ пройденную в этом круге карточку
        current_card = None
        for card in struggling_cards:
            if card.pk not in completed_ids:
                current_card = card
                break
        
        # Если все проблемные карточки пройдены в этом круге
        if current_card is None:
            # Очищаем сессию для нового круга
            self.request.session[session_key] = []
            current_card = struggling_cards[0]
        
        progress = UserCardProgress.objects.get(user=user, flashcard=current_card)
        stats = SRSEngine.get_statistics(user, deck)
        
        all_cards = list(deck.flashcard_set.filter(is_active=True))  # type: ignore[attr-defined]
        
        llm_service = LLMGeneratorService()
        exercise = llm_service.generate_exercise(
            card=current_card,
            exercise_type="auto",
            all_cards=all_cards
        )
        
        remaining_in_round = len([c for c in struggling_cards if c.pk not in completed_ids])
        if remaining_in_round == 0:
            remaining_in_round = len(struggling_cards)
        
        context.update({
            'deck': deck,
            'card': current_card,
            'progress': progress,
            'total_due': remaining_in_round,
            'stats': stats,
            'exercise': exercise,
            'session_completed': False,
            'is_retry_mode': True,
        })
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
        
        quality = 5 if is_correct else 3  # 3 вместо 2, чтобы меньше штрафовать при повторении
        SRSEngine.process_review(progress, quality)
        
        session_key = f'retry_session_{deck.pk}_completed'
        completed_ids = request.session.get(session_key, [])
        
        if card_id_int not in completed_ids:
            completed_ids.append(card_id_int)
            request.session[session_key] = completed_ids
        
        # Проверяем, есть ли ещё проблемные карточки
        all_progress = UserCardProgress.objects.filter(
            user=request.user,
            flashcard__deck=deck,
            flashcard__is_active=True
        )
        
        struggling_cards = []
        for p in all_progress:
            if not is_card_mastered(p):
                struggling_cards.append(p.flashcard)
        
        # Если проблемных карточек нет — завершаем
        if not struggling_cards:
            request.session.pop(session_key, None)
            return redirect('cards:retry_complete', deck_pk=deck.pk)
        
        # Проверяем, все ли проблемные карточки пройдены в этом круге
        struggling_ids = [c.pk for c in struggling_cards]
        all_completed_in_round = all(cid in completed_ids for cid in struggling_ids)
        
        if all_completed_in_round:
            # Завершили круг — показываем промежуточные результаты
            return redirect('cards:retry_results', deck_pk=deck.pk)
        
        # Продолжаем круг
        return redirect('cards:retry_struggling', deck_pk=deck.pk)


class RetryResultsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Промежуточные результаты после круга повторения.
    """
    template_name = 'cards/retry_results.html'
    
    def test_func(self) -> bool:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        return deck.owner == self.request.user  # type: ignore[attr-defined]
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        user = self.request.user
        
        stats = SRSEngine.get_statistics(user, deck)
        
        all_progress = UserCardProgress.objects.filter(
            user=user,
            flashcard__deck=deck,
            flashcard__is_active=True
        ).select_related('flashcard')
        
        mastered_cards = []
        struggling_cards = []
        
        for progress in all_progress:
            card_info = {
                'id': progress.flashcard.pk,
                'term': progress.flashcard.term,
                'definition': progress.flashcard.definition,
                'easiness_factor': round(progress.easiness_factor, 2),
                'consecutive_correct': progress.consecutive_correct,
                'total_errors': progress.total_errors,
            }
            
            if is_card_mastered(progress):
                mastered_cards.append(card_info)
            else:
                struggling_cards.append(card_info)
        
        context.update({
            'deck': deck,
            'stats': stats,
            'mastered_cards': mastered_cards,
            'struggling_cards': struggling_cards,
            'mastered_count': len(mastered_cards),
            'struggling_count': len(struggling_cards),
            'total_cards': len(mastered_cards) + len(struggling_cards),
            'is_retry_results': True,
        })
        return context


class RetryCompleteView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Все проблемные карточки освоены!
    """
    template_name = 'cards/retry_complete.html'
    
    def test_func(self) -> bool:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        return deck.owner == self.request.user  # type: ignore[attr-defined]
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        user = self.request.user
        
        stats = SRSEngine.get_statistics(user, deck)
        
        context.update({
            'deck': deck,
            'stats': stats,
        })
        return context