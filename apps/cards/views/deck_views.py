from typing import Any
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet, Count, Q
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    CreateView,
    DetailView,
    UpdateView,
    DeleteView,
)
from django.contrib import messages
from django.shortcuts import redirect
from django.views import View
from django.http import HttpResponse
from django import forms
from django.http import JsonResponse
from apps.cards.models import Deck, Flashcard
from django.shortcuts import get_object_or_404, redirect
from apps.cards.services.statistics import DeckProgressAggregator
from core.mixins import DeckAccessMixin, OwnerOrStaffMixin

class ToggleLikeView(LoginRequiredMixin, View):
    """Поставить/убрать лайк с колоды."""
    
    def post(self, request, deck_pk):
        deck = get_object_or_404(Deck, pk=deck_pk)
        
        if deck.owner == request.user:
            return JsonResponse({'success': False, 'error': 'Нельзя лайкнуть свою колоду'}, status=400)
        
        if request.user in deck.likes.all():  # type: ignore[attr-defined]
            deck.likes.remove(request.user)  # type: ignore[attr-defined]
            liked = False
        else:
            deck.likes.add(request.user)  # type: ignore[attr-defined]
            liked = True
        
        return JsonResponse({
            'success': True,
            'liked': liked,
            'likes_count': deck.likes.count()  # type: ignore[attr-defined]
        })


class CopyDeckView(LoginRequiredMixin, View):
    """Копирование публичной колоды себе."""

    def post(self, request: Any, deck_pk: int) -> HttpResponse:
        original_deck = get_object_or_404(Deck, pk=deck_pk, visibility="public")

        # Проверяем, не владелец ли это
        if original_deck.owner == request.user:  # type: ignore[attr-defined]
            messages.warning(request, "Это ваша колода, копировать не нужно.")
            return redirect("cards:deck_detail", pk=deck_pk)

        # Проверяем, нет ли уже копии
        existing = Deck.objects.filter(
            owner=request.user, name__startswith=f"Копия: {original_deck.name}"
        ).first()

        if existing:
            messages.info(
                request, f"У вас уже есть копия этой колоды: «{existing.name}»"
            )
            return redirect("cards:deck_detail", pk=existing.pk)

        # Создаем копию колоды
        new_deck = Deck.objects.create(
            name=f"Копия: {original_deck.name}",
            description=original_deck.description,
            owner=request.user,
            target_language=original_deck.target_language,
            native_language=original_deck.native_language,
            visibility="private",
        )

        # Копируем все карточки
        original_cards = original_deck.flashcard_set.filter(is_active=True)  # type: ignore[attr-defined]
        for card in original_cards:
            Flashcard.objects.create(
                deck=new_deck,
                term=card.term,
                definition=card.definition,
                part_of_speech=card.part_of_speech,
                example_sentence=card.example_sentence,
                base_difficulty=card.base_difficulty,
                is_active=True,
            )

        messages.success(
            request,
            f"✅ Колода «{original_deck.name}» сохранена! {original_cards.count()} карточек скопировано.",
        )
        return redirect("cards:deck_detail", pk=new_deck.pk)


class PublicDeckListView(LoginRequiredMixin, ListView):
    """Публичные колоды, доступные всем пользователям."""
    model = Deck
    template_name = 'cards/public_decks.html'
    context_object_name = 'decks'
    
    def get_queryset(self) -> QuerySet[Deck]:
        return Deck.objects.filter(visibility='public').annotate(
            likes_count=Count('likes')  # type: ignore[attr-defined]
        ).order_by('-likes_count', '-created_at').prefetch_related('flashcard_set', 'owner')  # type: ignore[attr-defined]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_staff'] = self.request.user.is_staff
        return context


class DeckListView(LoginRequiredMixin, ListView):
    """Список доступных колод (свои + публичные)."""

    model = Deck
    template_name = "cards/deck_list.html"
    context_object_name = "decks"

    def get_queryset(self) -> QuerySet[Deck]:
        user = self.request.user
        # Свои колоды + публичные колоды других пользователей
        return (Deck.objects.filter(owner=user) | Deck.objects.filter(visibility="public").exclude(owner=user)).distinct().prefetch_related("flashcard_set")  # type: ignore[attr-defined]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_staff"] = self.request.user.is_staff
        return context


class DeckCreateView(LoginRequiredMixin, CreateView):
    """Создание новой колоды (все пользователи могут выбирать видимость)."""

    model = Deck
    template_name = "cards/deck_form.html"
    success_url = reverse_lazy("cards:deck_list")

    def get_form_class(self):
        # ВСЕ пользователи могут выбирать видимость
        class UniversalDeckForm(forms.ModelForm):
            visibility = forms.ChoiceField(
                choices=Deck.VISIBILITY_CHOICES,
                widget=forms.RadioSelect,
                label="Видимость колоды",
                initial="private",
            )

            class Meta:
                model = Deck
                fields = [
                    "name",
                    "description",
                    "target_language",
                    "native_language",
                    "visibility",
                ]

        return UniversalDeckForm

    def form_valid(self, form: Any) -> HttpResponse:
        form.instance.owner = self.request.user
        return super().form_valid(form)


class DeckDetailView(LoginRequiredMixin, DeckAccessMixin, DetailView):
    """Детальная страница колоды (без изменений)."""

    model = Deck
    template_name = "cards/deck_detail.html"
    context_object_name = "deck"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = self.get_object()
        user = self.request.user

        context["is_owner"] = deck.owner == user  # type: ignore[attr-defined]
        context["can_edit"] = deck.owner == user or user.is_staff  # type: ignore[attr-defined]

        if hasattr(user, "is_authenticated") and user.is_authenticated:
            context["flashcards"] = deck.flashcard_set.filter(is_active=True)  # type: ignore[attr-defined]
            if deck.owner == user:  # type: ignore[attr-defined]
                context["progress"] = DeckProgressAggregator.get_or_create_progress(user, deck)  # type: ignore[arg-type]

        return context


class DeckUpdateView(LoginRequiredMixin, OwnerOrStaffMixin, UpdateView):
    """Редактирование колоды."""

    model = Deck
    template_name = "cards/deck_form.html"
    success_url = reverse_lazy("cards:deck_list")

    def get_form_class(self):
        class UniversalDeckForm(forms.ModelForm):
            visibility = forms.ChoiceField(
                choices=Deck.VISIBILITY_CHOICES,
                widget=forms.RadioSelect,
                label="Видимость колоды",
                initial="private",
            )

            class Meta:
                model = Deck
                fields = [
                    "name",
                    "description",
                    "target_language",
                    "native_language",
                    "visibility",
                ]

        return UniversalDeckForm


class DeckDeleteView(LoginRequiredMixin, OwnerOrStaffMixin, DeleteView):
    """Удаление колоды (без изменений)."""

    model = Deck
    template_name = "cards/deck_confirm_delete.html"
    success_url = reverse_lazy("cards:deck_list")
