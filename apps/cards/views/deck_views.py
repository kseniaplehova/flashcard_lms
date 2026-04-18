from typing import Any
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import QuerySet
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.http import HttpResponse
from apps.cards.models import Deck
from apps.cards.services.statistics import DeckProgressAggregator


class DeckListView(LoginRequiredMixin, ListView):
    """Список всех колод пользователя"""
    model = Deck
    template_name = 'cards/deck_list.html'
    context_object_name = 'decks'
    
    def get_queryset(self) -> QuerySet[Deck]:
        return Deck.objects.filter(owner=self.request.user).prefetch_related('flashcard_set')  # type: ignore[attr-defined]


class DeckCreateView(LoginRequiredMixin, CreateView):
    """Создание новой колоды"""
    model = Deck
    template_name = 'cards/deck_form.html'
    fields = ['name', 'description', 'target_language', 'native_language']
    success_url = reverse_lazy('cards:deck_list')
    
    def form_valid(self, form: Any) -> HttpResponse:
        form.instance.owner = self.request.user
        return super().form_valid(form)


class DeckDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Детальная страница колоды со списком карточек"""
    model = Deck
    template_name = 'cards/deck_detail.html'
    context_object_name = 'deck'
    
    def test_func(self) -> bool:
        deck: Deck = self.get_object()  # type: ignore[assignment]
        return deck.owner == self.request.user  # type: ignore[attr-defined]
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck: Deck = self.get_object()  # type: ignore[assignment]
        user = self.request.user
        
        if hasattr(user, 'is_authenticated') and user.is_authenticated:
            context['flashcards'] = deck.flashcard_set.filter(is_active=True)  # type: ignore[attr-defined]
            context['progress'] = DeckProgressAggregator.get_or_create_progress(user, deck)  # type: ignore[arg-type]
        
        return context


class DeckUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Редактирование колоды"""
    model = Deck
    template_name = 'cards/deck_form.html'
    fields = ['name', 'description', 'target_language', 'native_language']
    success_url = reverse_lazy('cards:deck_list')
    
    def test_func(self) -> bool:
        deck: Deck = self.get_object()  # type: ignore[assignment]
        return deck.owner == self.request.user  # type: ignore[attr-defined]


class DeckDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Удаление колоды"""
    model = Deck
    template_name = 'cards/deck_confirm_delete.html'
    success_url = reverse_lazy('cards:deck_list')
    
    def test_func(self) -> bool:
        deck: Deck = self.get_object()  # type: ignore[assignment]
        return deck.owner == self.request.user  # type: ignore[attr-defined]