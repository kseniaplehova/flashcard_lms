from django.utils import timezone
from datetime import timedelta


def get_date_range(days=7):
    """Получить диапазон дат для статистики."""
    end = timezone.now().date()
    start = end - timedelta(days=days)
    return start, end


def truncate_text(text, max_length=100):
    """Обрезать текст с многоточием."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + '...'