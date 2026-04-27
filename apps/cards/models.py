from django.contrib.auth import get_user_model
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class Deck(models.Model):
    """
    Логическая группа флеш-карт.
    Таблица: decks (см. sql/init.sql, строка 15)
    SQL: sql/queries.sql, строки 5-13
    """
    VISIBILITY_CHOICES = [
        ('private', 'Приватная'),
        ('public', 'Публичная'),
    ]
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True, default='')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='decks')
    likes = models.ManyToManyField(User, related_name='liked_decks', blank=True, verbose_name='Лайки')
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='private', db_index=True)
    is_public = models.BooleanField(default=False, db_index=True)
    target_language = models.CharField(max_length=50, default='en')
    native_language = models.CharField(max_length=50, default='ru')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'decks'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['owner', 'created_at'])]
        verbose_name = 'Колода'
        verbose_name_plural = 'Колоды'

    def __str__(self) -> str:
        return f"{self.name} (Owner: {self.owner.username if self.pk else 'Unknown'})"


class Flashcard(models.Model):
    """
    Атомарная единица контента.
    Таблица: flashcards (см. sql/init.sql, строка 25)
    SQL: sql/queries.sql, строки 18-24, 56-62
    """
    DIFFICULTY_CHOICES = [(1, 'Very Easy'), (2, 'Easy'), (3, 'Medium'), (4, 'Hard'), (5, 'Very Hard')]
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name='flashcard_set')
    term = models.CharField(max_length=255, db_index=True)
    definition = models.TextField()
    part_of_speech = models.CharField(max_length=50, blank=True, default='')
    example_sentence = models.TextField(blank=True, default='')
    base_difficulty = models.PositiveSmallIntegerField(choices=DIFFICULTY_CHOICES, default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    image_prompt = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'flashcards'
        ordering = ['term']
        indexes = [models.Index(fields=['deck', 'is_active']), models.Index(fields=['term', 'deck'])]
        verbose_name = 'Флеш-карта'
        verbose_name_plural = 'Флеш-карты'

    def __str__(self) -> str:
        return f"{self.term} -> {self.definition[:50]}"


class UserCardProgress(models.Model):
    """
    Хранилище состояния обучения (алгоритм SM-2).
    Таблица: user_card_progress (см. sql/init.sql, строка 38)
    SQL: sql/queries.sql, строки 26-36, 50-54
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='card_progress')
    flashcard = models.ForeignKey(Flashcard, on_delete=models.CASCADE, related_name='user_progress')
    repetition_number = models.PositiveSmallIntegerField(default=1)
    easiness_factor = models.FloatField(default=2.5, validators=[MinValueValidator(1.3), MaxValueValidator(2.5)])
    inter_repetition_interval = models.PositiveIntegerField(default=0)
    consecutive_correct = models.PositiveSmallIntegerField(default=0)
    total_attempts = models.PositiveIntegerField(default=0)
    total_errors = models.PositiveIntegerField(default=0)
    average_response_time_ms = models.PositiveIntegerField(default=0)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    next_review_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_quality_response = models.PositiveSmallIntegerField(default=0)
    requires_context_refresh = models.BooleanField(default=False)

    class Meta:
        db_table = 'user_card_progress'
        unique_together = [['user', 'flashcard']]
        indexes = [models.Index(fields=['user', 'next_review_at']), models.Index(fields=['user', 'requires_context_refresh'])]
        verbose_name = 'Прогресс по карточке'
        verbose_name_plural = 'Прогресс по карточкам'

    def __str__(self) -> str:
        return f"User {self.user.pk if self.pk else 0} | Card {self.flashcard.pk if self.pk else 0} | EF: {self.easiness_factor:.2f}"


class DeckProgress(models.Model):
    """
    Агрегированная статистика по колоде.
    Таблица: deck_progress (см. sql/init.sql, строка 52)
    SQL: sql/queries.sql, строки 40-48
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deck_progress')
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name='user_progress')
    cards_mastered = models.PositiveIntegerField(default=0)
    cards_learning = models.PositiveIntegerField(default=0)
    cards_struggling = models.PositiveIntegerField(default=0)
    last_session_at = models.DateTimeField(null=True, blank=True)
    total_time_spent_seconds = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'deck_progress'
        unique_together = [['user', 'deck']]
        indexes = [models.Index(fields=['user', 'updated_at'])]
        verbose_name = 'Прогресс по колоде'
        verbose_name_plural = 'Прогресс по колодам'

    def __str__(self) -> str:
        return f"User {self.user.pk if self.pk else 0} | Deck {self.deck.pk if self.pk else 0} | Mastered: {self.cards_mastered}"


class AIGenerationLog(models.Model):
    """
    Журнал запросов к LLM API.
    Таблица: ai_generation_logs (см. sql/init.sql, строка 77)
    """
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ai_requests')
    flashcard = models.ForeignKey(Flashcard, on_delete=models.SET_NULL, null=True, related_name='generation_logs')
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
        return f"User {self.user.pk if self.user else 0} | {self.model_used} | {'OK' if self.was_successful else 'FAIL'}"