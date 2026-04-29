from django.urls import path
from . import views
from .views import api_views

app_name = "cards"

urlpatterns = [
    # Dashboard
    path("", views.DashboardView.as_view(), name="dashboard"),
    # Deck CRUD
    path("decks/", views.DeckListView.as_view(), name="deck_list"),
    path("decks/public/", views.PublicDeckListView.as_view(), name="public_decks"),
    path("decks/create/", views.DeckCreateView.as_view(), name="deck_create"),
    path("decks/<int:pk>/", views.DeckDetailView.as_view(), name="deck_detail"),
    path("decks/<int:pk>/edit/", views.DeckUpdateView.as_view(), name="deck_update"),
    path("decks/<int:pk>/delete/", views.DeckDeleteView.as_view(), name="deck_delete"),
    # Flashcard CRUD
    path("decks/<int:deck_pk>/cards/create/", views.FlashcardCreateView.as_view(), name="card_create"),
    path("decks/<int:deck_pk>/cards/bulk-create/", views.FlashcardBulkCreateView.as_view(), name="card_bulk_create"),
    path("cards/<int:pk>/edit/", views.FlashcardUpdateView.as_view(), name="card_update"),
    path("cards/<int:pk>/delete/", views.FlashcardDeleteView.as_view(), name="card_delete"),
    # Study Session
    path("decks/<int:deck_pk>/study/", views.StudySessionView.as_view(), name="study_session"),
    path("decks/<int:deck_pk>/study/results/", views.StudyResultsView.as_view(), name="study_results"),
    path("decks/<int:deck_pk>/copy/", views.CopyDeckView.as_view(), name="copy_deck"),
    path("decks/<int:deck_pk>/like/", views.ToggleLikeView.as_view(), name="toggle_like"),
    # API
    path("api/cards/<int:card_pk>/review/", api_views.CardReviewAPIView.as_view(), name="api_card_review"),
    path("api/cards/<int:card_pk>/generate-context/", api_views.GenerateContextAPIView.as_view(), name="api_generate_context"),
    path("api/decks/<int:deck_pk>/stats/", api_views.DeckStatsAPIView.as_view(), name="api_deck_stats"),
    path("decks/<int:deck_pk>/study/retry/", views.RetryStrugglingView.as_view(), name="retry_struggling"),
    
    
]