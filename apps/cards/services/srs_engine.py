from datetime import timedelta
from typing import Dict, Any
from django.db.models import QuerySet, Q
from django.utils import timezone
from apps.cards.models import Deck, Flashcard, UserCardProgress, DeckProgress


class SRSEngine:
    """
    Реализация алгоритма интервального повторения SM-2 (SuperMemo 2).
    """
    
    @staticmethod
    def reset_all_progress(user, deck: Deck) -> None:
        """
        Сбрасывает прогресс всех карточек (для отладки).
        """
        now = timezone.now()
        UserCardProgress.objects.filter(
            user=user,
            flashcard__deck=deck
        ).update(
            next_review_at=now,
            repetition_number=0,
            easiness_factor=2.5,
            inter_repetition_interval=0,
            consecutive_correct=0,
            total_errors=0
        )
        print("DEBUG: All progress reset to now")
    
    @staticmethod
    def initialize_deck_progress(user, deck: Deck) -> int:
        """
        Инициализирует прогресс для всех активных карточек в колоде.
        Возвращает количество инициализированных карточек.
        """
        cards = deck.flashcard_set.filter(is_active=True)  # type: ignore[attr-defined]
        now = timezone.now()
        created_count = 0
        
        print(f"DEBUG INIT: cards count = {cards.count()}")
        
        for card in cards:
            progress, created = UserCardProgress.objects.get_or_create(
                user=user,
                flashcard=card,
                defaults={
                    'next_review_at': now,
                    'repetition_number': 0,
                    'easiness_factor': 2.5,
                    'inter_repetition_interval': 0,
                }
            )
            if created:
                created_count += 1
                print(f"DEBUG INIT: created progress for {card.term}, next_review = {now}")
            else:
                print(f"DEBUG INIT: progress exists for {card.term}, next_review = {progress.next_review_at}")
        
        SRSEngine._update_deck_progress(user, deck)
        
        return created_count
    
    @staticmethod
    def get_due_cards(user, deck: Deck) -> QuerySet[Flashcard]:
        """
        Возвращает карточки, готовые к повторению сегодня.
        """
        now = timezone.now()
        
        print(f"DEBUG SRS: now = {now}")
        print(f"DEBUG SRS: user = {user.username}")
        print(f"DEBUG SRS: deck = {deck.name}")
        
        all_progress = UserCardProgress.objects.filter(
            user=user,
            flashcard__deck=deck,
            flashcard__is_active=True
        )
        print(f"DEBUG SRS: total progress records = {all_progress.count()}")
        
        for p in all_progress:
            print(f"  - Card: {p.flashcard.term}, next_review: {p.next_review_at}, EF: {p.easiness_factor}")
        
        due_progress = UserCardProgress.objects.filter(
            user=user,
            flashcard__deck=deck,
            flashcard__is_active=True,
            next_review_at__lte=now
        ).select_related('flashcard').order_by('next_review_at')
        
        print(f"DEBUG SRS: due_progress count = {due_progress.count()}")
        
        return Flashcard.objects.filter(
            pk__in=due_progress.values('flashcard_id')
        )
    
    @staticmethod
    def process_review(progress: UserCardProgress, quality: int) -> UserCardProgress:
        """
        Обработка ответа пользователя (quality: 0-5).
        """
        if quality < 0 or quality > 5:
            raise ValueError('Quality must be between 0 and 5')
        
        progress.total_attempts += 1
        progress.last_quality_response = quality
        progress.last_reviewed_at = timezone.now()
        
        if quality >= 3:
            if progress.repetition_number == 0:
                progress.inter_repetition_interval = 1
            elif progress.repetition_number == 1:
                progress.inter_repetition_interval = 6
            else:
                progress.inter_repetition_interval = int(
                    progress.inter_repetition_interval * progress.easiness_factor
                )
            
            progress.repetition_number += 1
            progress.consecutive_correct += 1
        else:
            progress.repetition_number = 0
            progress.inter_repetition_interval = 1
            progress.consecutive_correct = 0
            progress.total_errors += 1
        
        progress.easiness_factor = max(
            1.3,
            progress.easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        )
        
        progress.next_review_at = timezone.now() + timedelta(days=progress.inter_repetition_interval)
        
        progress.requires_context_refresh = (
            progress.consecutive_correct == 0 and progress.total_errors >= 3
        )
        
        progress.save()
        
        SRSEngine._update_deck_progress(progress.user, progress.flashcard.deck)  # type: ignore[attr-defined]
        
        return progress
    
    @staticmethod
    def _update_deck_progress(user, deck: Deck) -> None:
        """
        Обновляет агрегированную статистику по колоде.
        """
        progress, _ = DeckProgress.objects.get_or_create(
            user=user,
            deck=deck
        )
        
        all_progress = UserCardProgress.objects.filter(
            user=user,
            flashcard__deck=deck,
            flashcard__is_active=True
        )
        
        progress.cards_mastered = all_progress.filter(
            easiness_factor__gte=2.3,
            inter_repetition_interval__gte=21
        ).count()
        
        progress.cards_learning = all_progress.filter(
            next_review_at__isnull=False
        ).exclude(
            easiness_factor__gte=2.3,
            inter_repetition_interval__gte=21
        ).count()
        
        struggling_filter = Q(easiness_factor__lt=1.7) | Q(consecutive_correct=0)
        progress.cards_struggling = all_progress.filter(struggling_filter).distinct().count()
        
        progress.save()
    
    @staticmethod
    def get_statistics(user, deck: Deck) -> Dict[str, Any]:
        """
        Возвращает статистику по колоде для отображения.
        """
        progress, _ = DeckProgress.objects.get_or_create(
            user=user,
            deck=deck
        )
        
        due_count = SRSEngine.get_due_cards(user, deck).count()
        total_cards = deck.flashcard_set.filter(is_active=True).count()  # type: ignore[attr-defined]
        
        mastered_percent = 0
        if total_cards > 0:
            mastered_percent = int(progress.cards_mastered / total_cards * 100)
        
        return {
            'total_cards': total_cards,
            'due_today': due_count,
            'mastered': progress.cards_mastered,
            'learning': progress.cards_learning,
            'struggling': progress.cards_struggling,
            'mastered_percent': mastered_percent,
        }