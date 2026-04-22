from django.contrib.auth import get_user_model
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class Deck(models.Model):
    """
    Логическая группа флеш-карт.
    Поддерживает категоризацию контента и изоляцию статистики.
    """
    VISIBILITY_CHOICES = [
        ('private', 'Приватная'),
        ('public', 'Публичная'),
    ]
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True, default='')
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='decks'
    )
    visibility = models.CharField(
        max_length=10,
        choices=VISIBILITY_CHOICES,
        default='private',
        db_index=True,
        help_text='Кто может видеть эту колоду'
    ) 
    
    is_public = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Публичная колода видна всем пользователям'
    )

    target_language = models.CharField(
        max_length=50,
        default='en',
        help_text='ISO 639-1 code'
    )
    native_language = models.CharField(
        max_length=50,
        default='ru',
        help_text='ISO 639-1 code'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'decks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'created_at']),
        ]
        verbose_name = 'Колода'
        verbose_name_plural = 'Колоды'

    def __str__(self) -> str:
        owner_username = self.owner.username if self.pk else 'Unknown'
        return f"{self.name} (Owner: {owner_username})"


class Flashcard(models.Model):
    """
    Атомарная единица контента.
    Содержит лексическую пару и метаданные для ИИ-генерации контекста.
    """
    DIFFICULTY_CHOICES = [
        (1, 'Very Easy'),
        (2, 'Easy'),
        (3, 'Medium'),
        (4, 'Hard'),
        (5, 'Very Hard'),
    ]

    deck = models.ForeignKey(
        Deck,
        on_delete=models.CASCADE,
        related_name='flashcard_set' 
    )
    term = models.CharField(max_length=255, db_index=True)
    definition = models.TextField()
    part_of_speech = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text='Noun, Verb, Adjective, etc.'
    )
    example_sentence = models.TextField(
        blank=True,
        default='',
        help_text='AI-generated contextual example'
    )
    base_difficulty = models.PositiveSmallIntegerField(
        choices=DIFFICULTY_CHOICES,
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    image_prompt = models.TextField(
        blank=True,
        default='',
        help_text='AI-generated prompt for DALL-E integration (future)'
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'flashcards'
        ordering = ['term']
        indexes = [
            models.Index(fields=['deck', 'is_active']),
            models.Index(fields=['term', 'deck']),
        ]
        verbose_name = 'Флеш-карта'
        verbose_name_plural = 'Флеш-карты'

    def __str__(self) -> str:
        return f"{self.term} -> {self.definition[:50]}"


class UserCardProgress(models.Model):
    """
    Хранилище состояния обучения для алгоритма Spaced Repetition.
    Реализует классическую модель SM-2 с расширениями для ИИ-адаптации.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='card_progress'
    )
    flashcard = models.ForeignKey(
        Flashcard,
        on_delete=models.CASCADE,
        related_name='user_progress'
    )
    
    repetition_number = models.PositiveSmallIntegerField(default=1)
    easiness_factor = models.FloatField(
        default=2.5,
        validators=[MinValueValidator(1.3), MaxValueValidator(2.5)]
    )
    inter_repetition_interval = models.PositiveIntegerField(
        default=0,
        help_text='Interval in days until next review'
    )
    
    consecutive_correct = models.PositiveSmallIntegerField(default=0)
    total_attempts = models.PositiveIntegerField(default=0)
    total_errors = models.PositiveIntegerField(default=0)
    average_response_time_ms = models.PositiveIntegerField(
        default=0,
        help_text='Average latency for correct answers'
    )
    
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    next_review_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Scheduled date for next repetition'
    )
    last_quality_response = models.PositiveSmallIntegerField(
        default=0,
        help_text='0-5 grade from user feedback'
    )
    
    requires_context_refresh = models.BooleanField(
        default=False,
        help_text='Set to True when consecutive_correct == 0 AND total_errors > 3'
    )

    class Meta:
        db_table = 'user_card_progress'
        unique_together = [['user', 'flashcard']]
        indexes = [
            models.Index(fields=['user', 'next_review_at']),
            models.Index(fields=['user', 'requires_context_refresh']),
        ]
        verbose_name = 'Прогресс по карточке'
        verbose_name_plural = 'Прогресс по карточкам'

    def __str__(self) -> str:
        user_pk = self.user.pk if self.pk else 0
        card_pk = self.flashcard.pk if self.pk else 0
        return f"User {user_pk} | Card {card_pk} | EF: {self.easiness_factor:.2f}"


class DeckProgress(models.Model):
    """
    Агрегированная статистика по колоде.
    Денормализация для быстрых аналитических срезов в UI.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='deck_progress'
    )
    deck = models.ForeignKey(
        Deck,
        on_delete=models.CASCADE,
        related_name='user_progress'
    )
    cards_mastered = models.PositiveIntegerField(
        default=0,
        help_text='Cards with EF >= 2.3 and interval >= 21 days'
    )
    cards_learning = models.PositiveIntegerField(
        default=0,
        help_text='Cards with interval < 21 days'
    )
    cards_struggling = models.PositiveIntegerField(
        default=0,
        help_text='Cards with EF < 1.7 or consecutive_correct == 0'
    )
    last_session_at = models.DateTimeField(null=True, blank=True)
    total_time_spent_seconds = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'deck_progress'
        unique_together = [['user', 'deck']]
        indexes = [
            models.Index(fields=['user', 'updated_at']),
        ]
        verbose_name = 'Прогресс по колоде'
        verbose_name_plural = 'Прогресс по колодам'

    def __str__(self) -> str:
        user_pk = self.user.pk if self.pk else 0
        deck_pk = self.deck.pk if self.pk else 0
        return f"User {user_pk} | Deck {deck_pk} | Mastered: {self.cards_mastered}"


class AIGenerationLog(models.Model):
    """
    Журнал запросов к LLM API.
    Критичен для мониторинга стоимости токенов и отладки промптов.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ai_requests'
    )
    flashcard = models.ForeignKey(
        Flashcard,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generation_logs'
    )
    request_prompt = models.TextField()
    response_content = models.TextField(blank=True, default='')
    model_used = models.CharField(max_length=100, default='gpt-4o-mini')
    tokens_used = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    was_successful = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'ai_generation_logs'
        ordering = ['-created_at']
        verbose_name = 'Лог ИИ-генерации'
        verbose_name_plural = 'Логи ИИ-генерации'

    def __str__(self) -> str:
        user_pk = self.user.pk if self.user else 0
        return f"User {user_pk} | {self.model_used} | {'OK' if self.was_successful else 'FAIL'}"