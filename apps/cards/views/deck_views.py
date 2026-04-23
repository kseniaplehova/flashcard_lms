from typing import Any
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.http import HttpResponse
from django import forms
from apps.cards.models import Deck
from apps.cards.services.statistics import DeckProgressAggregator
from core.mixins import DeckAccessMixin, OwnerOrStaffMixin


class DeckListView(LoginRequiredMixin, ListView):
    """Список доступных колод"""
    model = Deck
    template_name = 'cards/deck_list.html'
    context_object_name = 'decks'
    
    def get_queryset(self) -> QuerySet[Deck]:
        user = self.request.user
        if user.is_staff:
            return Deck.objects.filter(owner=user).prefetch_related('flashcard_set')  # type: ignore[attr-defined]
        else:
            return (Deck.objects.filter(owner=user) | Deck.objects.filter(visibility='public')).distinct().prefetch_related('flashcard_set')  # type: ignore[attr-defined]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_staff'] = self.request.user.is_staff
        return context


class DeckCreateView(LoginRequiredMixin, CreateView):
    """Создание новой колоды"""
    model = Deck
    template_name = 'cards/deck_form.html'
    success_url = reverse_lazy('cards:deck_list')
    
    def get_form_class(self):
        if self.request.user.is_staff:
            class AdminDeckForm(forms.ModelForm):
                visibility = forms.ChoiceField(
                    choices=Deck.VISIBILITY_CHOICES,
                    widget=forms.RadioSelect,
                    label='Видимость колоды',
                    initial='private'
                )
                class Meta:
                    model = Deck
                    fields = ['name', 'description', 'target_language', 'native_language', 'visibility']
            return AdminDeckForm
        else:
            class UserDeckForm(forms.ModelForm):
                class Meta:
                    model = Deck
                    fields = ['name', 'description', 'target_language', 'native_language']
            return UserDeckForm
    
    def form_valid(self, form: Any) -> HttpResponse:
        form.instance.owner = self.request.user
        return super().form_valid(form)


class DeckDetailView(LoginRequiredMixin, DeckAccessMixin, DetailView):
    """Детальная страница колоды"""
    model = Deck
    template_name = 'cards/deck_detail.html'
    context_object_name = 'deck'
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = self.get_object()
        user = self.request.user
        
        context['is_owner'] = deck.owner == user  # type: ignore[attr-defined]
        context['can_edit'] = deck.owner == user or user.is_staff  # type: ignore[attr-defined]
        
        if hasattr(user, 'is_authenticated') and user.is_authenticated:
            context['flashcards'] = deck.flashcard_set.filter(is_active=True)  # type: ignore[attr-defined]
            if deck.owner == user:  # type: ignore[attr-defined]
                context['progress'] = DeckProgressAggregator.get_or_create_progress(user, deck)  # type: ignore[arg-type]
        
        return context


class DeckUpdateView(LoginRequiredMixin, OwnerOrStaffMixin, UpdateView):
    """Редактирование колоды"""
    model = Deck
    template_name = 'cards/deck_form.html'
    success_url = reverse_lazy('cards:deck_list')
    
    def get_form_class(self):
        if self.request.user.is_staff:
            class AdminDeckForm(forms.ModelForm):
                visibility = forms.ChoiceField(
                    choices=Deck.VISIBILITY_CHOICES,
                    widget=forms.RadioSelect,
                    label='Видимость колоды',
                    initial='private'
                )
                class Meta:
                    model = Deck
                    fields = ['name', 'description', 'target_language', 'native_language', 'visibility']
            return AdminDeckForm
        else:
            class UserDeckForm(forms.ModelForm):
                class Meta:
                    model = Deck
                    fields = ['name', 'description', 'target_language', 'native_language']
            return UserDeckForm


class DeckDeleteView(LoginRequiredMixin, OwnerOrStaffMixin, DeleteView):
    """Удаление колоды"""
    model = Deck
    template_name = 'cards/deck_confirm_delete.html'
    success_url = reverse_lazy('cards:deck_list')