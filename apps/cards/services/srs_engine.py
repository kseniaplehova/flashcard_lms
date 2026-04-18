from datetime import timedelta
from typing import Optional
from django.db.models import QuerySet
from django.utils import timezone
from apps.cards.models import Deck, Flashcard, UserCardProgress


class SRSEngine:
    """
    Реализация алгоритма интервального повторения SM-2.
    """
    
    @staticmethod
    def get_due_cards(user, deck: Deck) -> QuerySet[Flashcard]:
        """
        Возвращает карточки, готовые к повторению сегодня.
        """
        now = timezone.now()
        
        progress_without_schedule = UserCardProgress.objects.filter(
            user=user,
            flashcard__deck=deck,
            flashcard__is_active=True,
            next_review_at__isnull=True,
        )
        
        for progress in progress_without_schedule:
            progress.next_review_at = now
            progress.save(update_fields=['next_review_at'])
        
        due_progress = UserCardProgress.objects.filter(
            user=user,
            flashcard__deck=deck,
            flashcard__is_active=True,
            next_review_at__lte=now,
        ).select_related('flashcard')
        
        return Flashcard.objects.filter(
            pk__in=due_progress.values('flashcard_id')
        ).order_by('?')
    
    @staticmethod
    def process_review(progress: UserCardProgress, quality: int) -> UserCardProgress:
        """
        Обработка ответа пользователя (quality: 0-5).
        Обновляет параметры SM-2.
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
            progress.consecutive_correct == 0 and progress.total_errors > 3
        )
        
        progress.save()
        return progress