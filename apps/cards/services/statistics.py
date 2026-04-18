from typing import Union
from django.contrib.auth.models import AnonymousUser
from apps.cards.models import Deck, DeckProgress
from apps.accounts.models import User


class DeckProgressAggregator:
    """
    Агрегация статистики по колоде.
    """
    
    @staticmethod
    def get_or_create_progress(user: Union[User, AnonymousUser], deck: Deck) -> DeckProgress:
        """
        Возвращает или создает прогресс по колоде.
        """
        if isinstance(user, AnonymousUser):
            raise ValueError("Cannot create progress for anonymous user")
        
        progress, _ = DeckProgress.objects.get_or_create(
            user=user,
            deck=deck
        )
        return progress