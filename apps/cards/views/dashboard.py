from typing import Any
from collections import defaultdict
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from apps.cards.models import Deck, DeckProgress


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Главный дашборд пользователя.
    """
    template_name = 'cards/dashboard.html'
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        decks = Deck.objects.filter(owner=user).prefetch_related('user_progress', 'flashcard_set')  # type: ignore[attr-defined]
        context['decks'] = decks
        context['total_cards'] = sum(deck.flashcard_set.count() for deck in decks)  # type: ignore[attr-defined]
        
        # Группировка по языкам
        language_groups = defaultdict(list)
        for deck in decks:
            lang = deck.target_language.lower()
            language_groups[lang].append(deck)
        context['language_groups'] = dict(sorted(language_groups.items()))
        
        deck_progress = DeckProgress.objects.filter(user=user)  # type: ignore[attr-defined]
        context['mastered_total'] = sum(p.cards_mastered for p in deck_progress)
        context['learning_total'] = sum(p.cards_learning for p in deck_progress)
        
        return context