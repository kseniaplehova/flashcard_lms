from .dashboard import DashboardView
from .deck_views import (
    DeckListView,
    PublicDeckListView,
    DeckCreateView,
    DeckDetailView,
    DeckUpdateView,
    DeckDeleteView,
    CopyDeckView,
    ToggleLikeView,
)
from .card_views import (
    FlashcardCreateView,
    FlashcardBulkCreateView,
    FlashcardUpdateView,
    FlashcardDeleteView,
)
from .study_views import (
    StudySessionView,
    StudyResultsView,
)

from .study_views import (
    StudySessionView,
    StudyResultsView,
    RetryStrugglingView,
)
__all__ = [
    "DashboardView",
    "DeckListView",
    "PublicDeckListView",
    "DeckCreateView",
    "DeckDetailView",
    "DeckUpdateView",
    "DeckDeleteView",
    "CopyDeckView",
    "ToggleLikeView",
    "FlashcardCreateView",
    "FlashcardBulkCreateView",
    "FlashcardUpdateView",
    "FlashcardDeleteView",
    "StudySessionView",
    "StudyResultsView",
]