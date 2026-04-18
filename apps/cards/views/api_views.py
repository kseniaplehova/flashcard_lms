import json
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views import View
from apps.cards.models import Deck, Flashcard, UserCardProgress, DeckProgress
from apps.cards.services.llm_generator import LLMGenerator
from apps.cards.services.srs_engine import SRSEngine


class CardReviewAPIView(LoginRequiredMixin, View):
    """
    API эндпоинт для обработки ответа пользователя на карточку.
    Вызывается через fetch() из JavaScript.
    """
    def post(self, request: HttpRequest, card_pk: int) -> JsonResponse:
        try:
            data = json.loads(request.body)
            quality = int(data.get('quality', 0))
            
            card = get_object_or_404(Flashcard, pk=card_pk)
            progress, _ = UserCardProgress.objects.get_or_create(
                user=request.user,
                flashcard=card,
                defaults={'next_review_at': timezone.now()}
            )
            
            updated_progress = SRSEngine.process_review(progress, quality)
            
            return JsonResponse({
                'success': True,
                'easiness_factor': updated_progress.easiness_factor,
                'interval': updated_progress.inter_repetition_interval,
                'next_review_at': updated_progress.next_review_at.isoformat() if updated_progress.next_review_at else None,
                'requires_context_refresh': updated_progress.requires_context_refresh,
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class GenerateContextAPIView(LoginRequiredMixin, View):
    """
    API эндпоинт для генерации контекстного примера через LLM.
    Вызывается асинхронно при нажатии кнопки "Сгенерировать пример".
    """
    def post(self, request: HttpRequest, card_pk: int) -> JsonResponse:
        card = get_object_or_404(Flashcard, pk=card_pk)
        
        if card.deck.owner != request.user:  # type: ignore[attr-defined]
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        
        try:
            generated_data = LLMGenerator.generate_example_sentence(
                term=card.term,
                definition=card.definition,
                part_of_speech=card.part_of_speech,
                target_language=card.deck.target_language,  # type: ignore[attr-defined]
                user=request.user,  # type: ignore[arg-type]
                flashcard=card,
            )
            
            if generated_data.get('example'):
                card.example_sentence = generated_data['example']
                card.save(update_fields=['example_sentence', 'updated_at'])
            
            return JsonResponse({
                'success': True,
                'example': card.example_sentence,
                'tokens_used': generated_data.get('tokens_used', 0),
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class DeckStatsAPIView(LoginRequiredMixin, View):
    """
    API эндпоинт для получения статистики по колоде.
    Используется для обновления дашборда без перезагрузки страницы.
    """
    def get(self, request: HttpRequest, deck_pk: int) -> JsonResponse:
        deck = get_object_or_404(Deck, pk=deck_pk)
        
        if deck.owner != request.user:  # type: ignore[attr-defined]
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        
        progress, _ = DeckProgress.objects.get_or_create(
            user=request.user,  # type: ignore[arg-type]
            deck=deck
        )
        
        due_count = SRSEngine.get_due_cards(request.user, deck).count()
        total_cards = deck.flashcard_set.filter(is_active=True).count()  # type: ignore[attr-defined]
        
        return JsonResponse({
            'success': True,
            'deck_id': deck.pk,
            'deck_name': deck.name,
            'total_cards': total_cards,
            'cards_mastered': progress.cards_mastered,
            'cards_learning': progress.cards_learning,
            'cards_struggling': progress.cards_struggling,
            'due_today': due_count,
        })