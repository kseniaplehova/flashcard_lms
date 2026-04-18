from typing import Any
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import TemplateView
from django.http import HttpResponse
from apps.cards.models import Deck, Flashcard, UserCardProgress
from apps.cards.services.srs_engine import SRSEngine


class StudySessionView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Учебная сессия по колоде.
    """
    template_name = 'cards/study_session.html'
    
    def test_func(self) -> bool:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        return deck.owner == self.request.user  # type: ignore[attr-defined]
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        user = self.request.user
        
        due_cards = SRSEngine.get_due_cards(user, deck)
        
        if not due_cards.exists():
            context['no_cards'] = True
            context['deck'] = deck
            return context
        
        current_card = due_cards.first()
        progress, _ = UserCardProgress.objects.get_or_create(
            user=user,  # type: ignore[arg-type]
            flashcard=current_card,
            defaults={'next_review_at': timezone.now()}
        )
        
        context.update({
            'deck': deck,
            'card': current_card,
            'progress': progress,
            'total_due': due_cards.count(),
            'session_completed': False,
        })
        return context
    
    def post(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        card_id = request.POST.get('card_id')
        quality = int(request.POST.get('quality', 0))
        
        card = get_object_or_404(Flashcard, pk=card_id, deck=deck)
        progress = UserCardProgress.objects.get(user=request.user, flashcard=card)
        
        SRSEngine.process_review(progress, quality)
        
        if 'next' in request.POST:
            return redirect('cards:study_session', deck_pk=deck.pk)
        
        return redirect('cards:deck_detail', pk=deck.pk)