from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Кастомная модель пользователя.
    """
    is_teacher = models.BooleanField(
        default=False,
        help_text='Может создавать публичные колоды и управлять пользователями'
    )
    current_streak = models.PositiveIntegerField(default=0, verbose_name='Дней подряд')
    last_activity_date = models.DateField(null=True, blank=True, verbose_name='Последняя активность')
    
    class Meta:
        db_table = 'users'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self) -> str:
        return self.username or self.email or f"User #{self.pk}"
    

class UserActivity(models.Model):
    """
    Отслеживание активности пользователей.
    Таблица: user_activities (см. sql/init.sql, строка 67)
    Запросы: sql/admin_queries.sql, строки 10-30
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    action = models.CharField(
        max_length=50,
        choices=[
            ('login', 'Вход в систему'),
            ('logout', 'Выход'),
            ('study_start', 'Начало обучения'),
            ('study_complete', 'Завершение обучения'),
            ('deck_create', 'Создание колоды'),
            ('card_create', 'Создание карточки'),
        ]
    )
    deck = models.ForeignKey(
        'cards.Deck',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'user_activities'
        ordering = ['-created_at']
        verbose_name = 'Активность пользователя'
        verbose_name_plural = 'Активности пользователей'
    
    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.created_at.strftime('%d.%m.%Y %H:%M')}"