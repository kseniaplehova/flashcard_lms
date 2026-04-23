from typing import Any
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import CreateView, UpdateView, DeleteView, View
from django.http import HttpResponse
from apps.cards.models import Deck, Flashcard
from apps.cards.services.llm_generator import LLMGeneratorService


class FlashcardCreateView(LoginRequiredMixin, CreateView):
    """Создание одной карточки с авто-генерацией."""
    model = Flashcard
    template_name = 'cards/flashcard_form.html'
    fields = ['term']
    
    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        # Проверка доступа к колоде
        if not (deck.owner == request.user or request.user.is_staff or deck.visibility == 'public'):  # type: ignore[attr-defined]
            messages.error(request, "У вас нет доступа к этой колоде.")
            return redirect('cards:deck_list')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        term = form.cleaned_data['term']
        
        try:
            llm_service = LLMGeneratorService()
            generated = llm_service.generate_example_sentence(
                term=term,
                definition='',
                part_of_speech='',
                target_language=deck.target_language,
                user=self.request.user,  # type: ignore[arg-type]
                flashcard=None,
            )
            
            form.instance.definition = f"Перевод: {term}"
            form.instance.example_sentence = generated.get('example', '')
            messages.success(self.request, f"✅ Карточка '{term}' создана!")
        except Exception as e:
            form.instance.definition = term
            messages.error(self.request, f"❌ Ошибка генерации: {str(e)}")
        
        form.instance.deck = deck
        return super().form_valid(form)
    
    def get_success_url(self) -> str:
        return reverse('cards:deck_detail', kwargs={'pk': self.kwargs['deck_pk']})
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['deck'] = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        return context


class FlashcardBulkCreateView(LoginRequiredMixin, View):
    """Массовое создание карточек по теме через ИИ."""
    template_name = 'cards/flashcard_bulk_form.html'
    
    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=self.kwargs['deck_pk'])
        if not (deck.owner == request.user or request.user.is_staff or deck.visibility == 'public'):  # type: ignore[attr-defined]
            messages.error(request, "У вас нет доступа к этой колоде.")
            return redirect('cards:deck_list')
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request: Any, deck_pk: int) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=deck_pk)
        return render(request, self.template_name, {'deck': deck})
    
    def post(self, request: Any, deck_pk: int) -> HttpResponse:
        deck = get_object_or_404(Deck, pk=deck_pk)
        topic = request.POST.get('topic', '').strip()
        
        try:
            count = int(request.POST.get('count', 10))
        except ValueError:
            count = 10
        
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
                term = str(card_data.get('term', '')).strip()
                translation = str(card_data.get('translation', '')).strip()
                
                if term and translation:
                    Flashcard.objects.create(
                        deck=deck,
                        term=term,
                        definition=translation,
                        part_of_speech=str(card_data.get('part_of_speech', '')),
                        example_sentence=str(card_data.get('example', '')),
                        base_difficulty=3
                    )
                    created_count += 1
                    total_tokens += card_data.get('tokens_used', 0)
            
            if created_count > 0:
                messages.success(request, f"✅ Создано {created_count} карточек по теме «{topic}»!")
            else:
                messages.warning(request, "⚠️ Не удалось создать карточки. Попробуйте другую тему.")
            
        except Exception as e:
            messages.error(request, f"❌ Ошибка генерации: {str(e)}")
        
        return redirect('cards:deck_detail', pk=deck_pk)


class FlashcardUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование флеш-карты"""
    model = Flashcard
    template_name = 'cards/flashcard_form.html'
    fields = ['term', 'definition', 'part_of_speech', 'base_difficulty', 'example_sentence', 'is_active']
    
    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        flashcard = self.get_object()
        if not (flashcard.deck.owner == request.user or request.user.is_staff):  # type: ignore[attr-defined, union-attr]
            return redirect('cards:deck_detail', pk=flashcard.deck.pk)  # type: ignore[attr-defined, union-attr]
        return super().dispatch(request, *args, **kwargs)
    
    def get_success_url(self) -> str:
        flashcard: Flashcard = self.object  # type: ignore[assignment]
        return reverse('cards:deck_detail', kwargs={'pk': flashcard.deck.pk})
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        flashcard: Flashcard = self.object  # type: ignore[assignment]
        context['deck'] = flashcard.deck
        return context


class FlashcardDeleteView(LoginRequiredMixin, DeleteView):
    """Удаление флеш-карты"""
    model = Flashcard
    template_name = 'cards/flashcard_confirm_delete.html'
    
    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        flashcard = self.get_object()
        if not (flashcard.deck.owner == request.user or request.user.is_staff):  # type: ignore[attr-defined, union-attr]
            return redirect('cards:deck_detail', pk=flashcard.deck.pk)  # type: ignore[attr-defined, union-attr]
        return super().dispatch(request, *args, **kwargs)
    
    def get_success_url(self) -> str:
        flashcard: Flashcard = self.object  # type: ignore[assignment]
        return reverse('cards:deck_detail', kwargs={'pk': flashcard.deck.pk})