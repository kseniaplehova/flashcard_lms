from typing import Any
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet, Count
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, View
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django import forms
from collections import defaultdict

from apps.cards.models import Deck, Flashcard
from apps.cards.services.statistics import DeckProgressAggregator
from core.mixins import DeckAccessMixin, OwnerOrStaffMixin


class ToggleLikeView(LoginRequiredMixin, View):
    """
    Поставить/убрать лайк с колоды.
    SQL: sql/queries.sql, строка 68 (INSERT/DELETE deck_likes)
    """
    def post(self, request, deck_pk):
        deck = get_object_or_404(Deck, pk=deck_pk)
        if deck.owner == request.user:
            return JsonResponse({"success": False, "error": "Нельзя лайкнуть свою колоду"}, status=400)
        if request.user in deck.likes.all():
            deck.likes.remove(request.user)
            liked = False
        else:
            deck.likes.add(request.user)
            liked = True
        return JsonResponse({"success": True, "liked": liked, "likes_count": deck.likes.count()})


class CopyDeckView(LoginRequiredMixin, View):
    """
    Копирование публичной колоды себе.
    SQL: sql/queries.sql, строка 56 (INSERT INTO decks ... SELECT)
    """
    def post(self, request: Any, deck_pk: int) -> HttpResponse:
        original_deck = get_object_or_404(Deck, pk=deck_pk, visibility="public")
        if original_deck.owner == request.user:
            messages.warning(request, "Это ваша колода, копировать не нужно.")
            return redirect("cards:deck_detail", pk=deck_pk)

        existing = Deck.objects.filter(owner=request.user, name__startswith=f"Копия: {original_deck.name}").first()
        if existing:
            messages.info(request, f"У вас уже есть копия: «{existing.name}»")
            return redirect("cards:deck_detail", pk=existing.pk)

        new_deck = Deck.objects.create(name=f"Копия: {original_deck.name}", description=original_deck.description,
                                        owner=request.user, target_language=original_deck.target_language,
                                        native_language=original_deck.native_language, visibility="private")
        for card in original_deck.flashcard_set.filter(is_active=True):
            Flashcard.objects.create(deck=new_deck, term=card.term, definition=card.definition,
                                      part_of_speech=card.part_of_speech, example_sentence=card.example_sentence,
                                      base_difficulty=card.base_difficulty, is_active=True)
        messages.success(request, f"Колода «{original_deck.name}» сохранена!")
        return redirect("cards:deck_detail", pk=new_deck.pk)


class PublicDeckListView(LoginRequiredMixin, ListView):
    """
    Публичные колоды.
    SQL: sql/queries.sql, строка 8 (SELECT ... LEFT JOIN deck_likes)
    """
    model = Deck
    template_name = "cards/public_decks.html"
    context_object_name = "decks"

    def get_queryset(self) -> QuerySet[Deck]:
        return Deck.objects.filter(visibility="public").annotate(likes_count=Count("likes")).order_by("-likes_count", "-created_at").prefetch_related("flashcard_set", "owner")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_staff"] = self.request.user.is_staff
        language_groups = defaultdict(list)
        for deck in context["decks"]:
            language_groups[deck.target_language.lower()].append(deck)
        context["language_groups"] = dict(sorted(language_groups.items()))
        return context


class DeckListView(LoginRequiredMixin, ListView):
    """
    Список своих колод.
    SQL: sql/queries.sql, строка 5 (SELECT * FROM decks WHERE owner_id = ?)
    """
    model = Deck
    template_name = "cards/deck_list.html"
    context_object_name = "decks"

    def get_queryset(self) -> QuerySet[Deck]:
        return Deck.objects.filter(owner=self.request.user).prefetch_related("flashcard_set")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_staff"] = self.request.user.is_staff
        context["current_lang"] = self.request.GET.get("lang", "")
        languages = Deck.objects.filter(owner=self.request.user).values_list("target_language", flat=True).distinct().order_by("target_language")
        context["available_languages"] = languages
        return context


class DeckCreateView(LoginRequiredMixin, CreateView):
    """
    Создание новой колоды.
    SQL: INSERT INTO decks (...) VALUES (...)
    """
    model = Deck
    template_name = "cards/deck_form.html"
    LANGUAGE_CHOICES = [("en", "English"), ("es", "Español"), ("fr", "Français"), ("de", "Deutsch"), ("it", "Italiano"), ("pt", "Português"), ("ja", "日本語"), ("ko", "한국어"), ("zh", "中文"), ("ru", "Русский")]

    def get_form_class(self):
        class Form(forms.ModelForm):
            target_language = forms.ChoiceField(choices=self.LANGUAGE_CHOICES, label="Язык изучения", initial="en")
            native_language = forms.ChoiceField(choices=self.LANGUAGE_CHOICES, label="Родной язык", initial="ru")
            visibility = forms.ChoiceField(choices=Deck.VISIBILITY_CHOICES, widget=forms.RadioSelect, label="Видимость колоды", initial="private")
            class Meta:
                model = Deck
                fields = ["name", "description", "target_language", "native_language", "visibility"]
        return Form

    def form_valid(self, form: Any) -> HttpResponse:
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f"Колода «{self.object.name}» создана!")
        return response

    def get_success_url(self) -> str:
        return reverse("cards:deck_update", kwargs={"pk": self.object.pk})


class DeckDetailView(LoginRequiredMixin, DeckAccessMixin, DetailView):
    """Детальная страница колоды."""
    model = Deck
    template_name = "cards/deck_detail.html"
    context_object_name = "deck"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        deck = self.get_object()
        user = self.request.user
        context["is_owner"] = deck.owner == user
        context["can_edit"] = deck.owner == user or user.is_staff
        if user.is_authenticated:
            context["flashcards"] = deck.flashcard_set.filter(is_active=True)
            if deck.owner == user:
                context["progress"] = DeckProgressAggregator.get_or_create_progress(user, deck)
        return context


class DeckUpdateView(LoginRequiredMixin, OwnerOrStaffMixin, UpdateView):
    """Редактирование колоды."""
    model = Deck
    template_name = "cards/deck_form.html"
    success_url = reverse_lazy("cards:deck_list")
    LANGUAGE_CHOICES = [("en", "English"), ("es", "Español"), ("fr", "Français"), ("de", "Deutsch"), ("it", "Italiano"), ("pt", "Português"), ("ja", "日本語"), ("ko", "한국어"), ("zh", "中文"), ("ru", "Русский")]

    def get_form_class(self):
        class Form(forms.ModelForm):
            target_language = forms.ChoiceField(choices=self.LANGUAGE_CHOICES, label="Язык изучения")
            native_language = forms.ChoiceField(choices=self.LANGUAGE_CHOICES, label="Родной язык")
            visibility = forms.ChoiceField(choices=Deck.VISIBILITY_CHOICES, widget=forms.RadioSelect, label="Видимость колоды", initial="private")
            class Meta:
                model = Deck
                fields = ["name", "description", "target_language", "native_language", "visibility"]
        return Form


class DeckDeleteView(LoginRequiredMixin, OwnerOrStaffMixin, DeleteView):
    """Удаление колоды."""
    model = Deck
    template_name = "cards/deck_confirm_delete.html"
    success_url = reverse_lazy("cards:deck_list")