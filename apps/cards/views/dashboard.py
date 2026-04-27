from typing import Any
from collections import defaultdict
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from apps.cards.models import Deck, DeckProgress


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Главный дашборд пользователя.
    SQL: sql/queries.sql, строка 5 (SELECT * FROM decks WHERE owner_id = ?)
    SQL: sql/queries.sql, строка 40 (SELECT SUM(...) FROM deck_progress WHERE user_id = ?)
    """
    template_name = 'cards/dashboard.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # SQL: SELECT * FROM decks WHERE owner_id = ? (строка 5)
        decks = Deck.objects.filter(owner=user).prefetch_related('user_progress', 'flashcard_set')
        context['decks'] = decks
        context['total_cards'] = sum(deck.flashcard_set.count() for deck in decks)

        # Группировка по языкам для отображения
        language_groups = defaultdict(list)
        for deck in decks:
            language_groups[deck.target_language.lower()].append(deck)
        context['language_groups'] = dict(sorted(language_groups.items()))

        # SQL: SELECT SUM(cards_mastered), SUM(cards_learning) FROM deck_progress WHERE user_id = ? (строка 40)
        deck_progress = DeckProgress.objects.filter(user=user)
        context['mastered_total'] = sum(p.cards_mastered for p in deck_progress)
        context['learning_total'] = sum(p.cards_learning for p in deck_progress)

        return context