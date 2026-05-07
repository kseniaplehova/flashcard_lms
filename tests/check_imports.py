import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

imports = [
    "from apps.cards.models import Flashcard, Deck, UserCardProgress, DeckProgress, AIGenerationLog",
    "from apps.accounts.models import User",
    "from apps.cards.services.llm_generator import LLMGeneratorService",
    "from apps.cards.services.exercise_engine import ExerciseEngine",
    "from apps.cards.services.statistics import DeckProgressAggregator",
    "from core.exceptions import CardGenerationError, AIAPIError",
]

print("=" * 50)
print("ПРОВЕРКА ИМПОРТОВ ДЛЯ ТЕСТОВ")
print("=" * 50)

for attempt in imports:
    try:
        exec(attempt)
        print(f"✓ {attempt.split(' import ')[1]}")
    except ImportError as e:
        print(f"✗ Ошибка: {e}")
    except Exception as e:
        print(f"! Другая ошибка: {e}")

print("=" * 50)
print("ГОТОВО")