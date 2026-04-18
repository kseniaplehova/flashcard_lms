from typing import Any
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import CreateView, UpdateView, DeleteView, View
from django.http import HttpResponse
from apps.cards.models import Deck, Flashcard
from apps.cards.services.llm_generator import LLMGeneratorService


class FlashcardCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Создание одной карточки с авто-генерацией."""
    model = Flashcard
    template_name = 'cards/flashcard_form.html'
    fields = ['term']
    
    def test_func(self) -> bool:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        return deck.owner == self.request.user  # type: ignore[attr-defined]
    
    def form_valid(self, form: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        term = form.cleaned_data['term']
        
        try:
            llm_service = LLMGeneratorService()
            generated = llm_service.generate_card_content(
                term=term,
                target_lang=deck.target_language,
                native_lang=deck.native_language
            )
            
            if 'error' not in generated:
                form.instance.definition = generated.get('translation', term)
                form.instance.part_of_speech = generated.get('part_of_speech', '')
                form.instance.example_sentence = generated.get('example', '')
                messages.success(
                    self.request, 
                    f"✅ Карточка создана! Токенов: {generated.get('tokens_used', 0)}"
                )
            else:
                form.instance.definition = term
                messages.warning(self.request, f"⚠️ ИИ недоступен: {generated['error']}")
        except Exception as e:
            form.instance.definition = term
            messages.error(self.request, f"❌ Ошибка: {str(e)}")
        
        form.instance.deck = deck
        return super().form_valid(form)
    
    def get_success_url(self) -> str:
        return reverse('cards:deck_detail', kwargs={'pk': self.kwargs['deck_pk']})
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['deck'] = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        return context


class FlashcardBulkCreateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Массовое создание карточек по теме через ИИ."""
    template_name = 'cards/flashcard_bulk_form.html'
    
    def test_func(self) -> bool:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        return deck.owner == self.request.user  # type: ignore[attr-defined]
    
    def get(self, request, deck_pk: int):
        deck = get_object_or_404(Deck, pk=deck_pk)
        return render(request, self.template_name, {'deck': deck})
    
    def post(self, request, deck_pk: int):
        deck = get_object_or_404(Deck, pk=deck_pk)
        topic = request.POST.get('topic', '').strip()
        count = int(request.POST.get('count', 10))
        
        if not topic:
            messages.error(request, "Введите тему для генерации")
            return render(request, self.template_name, {'deck': deck})
        
        try:
            llm_service = LLMGeneratorService()
            cards_data = llm_service.generate_cards_by_topic(
                topic=topic,
                count=count,
                target_lang=deck.target_language,
                native_lang=deck.native_language
            )
            
            created_count = 0
            total_tokens = 0
            
            for card_data in cards_data:
                if card_data.get('term') and card_data.get('translation'):
                    Flashcard.objects.create(
                        deck=deck,
                        term=card_data['term'],
                        definition=card_data['translation'],
                        part_of_speech=card_data.get('part_of_speech', ''),
                        example_sentence=card_data.get('example', ''),
                        base_difficulty=3
                    )
                    created_count += 1
                    total_tokens += card_data.get('tokens_used', 0)
            
            messages.success(
                request,
                f"✅ Создано {created_count} карточек по теме «{topic}»! "
                f"Использовано токенов: {total_tokens}"
            )
            
        except Exception as e:
            messages.error(request, f"❌ Ошибка генерации: {str(e)}")
        
        return redirect('cards:deck_detail', pk=deck_pk)


class FlashcardUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Редактирование флеш-карты"""
    model = Flashcard
    template_name = 'cards/flashcard_form.html'
    fields = ['term', 'definition', 'part_of_speech', 'base_difficulty', 'example_sentence', 'is_active']
    
    def test_func(self) -> bool:
        flashcard: Flashcard = self.get_object()  # type: ignore[assignment]
        return flashcard.deck.owner == self.request.user  # type: ignore[attr-defined]
    
    def get_success_url(self) -> str:
        flashcard: Flashcard = self.object  # type: ignore[assignment]
        return reverse('cards:deck_detail', kwargs={'pk': flashcard.deck.pk})
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        flashcard: Flashcard = self.object  # type: ignore[assignment]
        context['deck'] = flashcard.deck
        return context


class FlashcardDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Удаление флеш-карты"""
    model = Flashcard
    template_name = 'cards/flashcard_confirm_delete.html'
    
    def test_func(self) -> bool:
        flashcard: Flashcard = self.get_object()  # type: ignore[assignment]
        return flashcard.deck.owner == self.request.user  # type: ignore[attr-defined]
    
    def get_success_url(self) -> str:
        flashcard: Flashcard = self.object  # type: ignore[assignment]
        return reverse('cards:deck_detail', kwargs={'pk': flashcard.deck.pk})