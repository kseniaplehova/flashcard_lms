import random
from typing import Dict, Any, List
from apps.cards.models import Flashcard


class ExerciseEngine:
    """
    Генератор разных типов упражнений.
    """
    
    @staticmethod
    def get_random_exercise_type() -> str:
        """Случайный тип упражнения."""
        return random.choice(['multiple_choice', 'typing', 'flashcard'])
    
    @staticmethod
    def generate_multiple_choice(card: Flashcard, all_cards: List[Flashcard]) -> Dict[str, Any]:
        """
        Генерирует вопрос с выбором правильного перевода.
        """
        correct = card.definition
        # Выбираем 3 случайных неправильных ответа
        other_cards = [c for c in all_cards if c.pk != card.pk]
        wrong_answers = random.sample([c.definition for c in other_cards], min(3, len(other_cards)))
        
        options = wrong_answers + [correct]
        random.shuffle(options)
        
        return {
            'type': 'multiple_choice',
            'question': f'Выберите правильный перевод: {card.term}',
            'options': options,
            'correct': correct,
            'card_id': card.pk,
        }
    
    @staticmethod
    def generate_typing_exercise(card: Flashcard) -> Dict[str, Any]:
        """
        Генерирует упражнение на ввод перевода с клавиатуры.
        """
        return {
            'type': 'typing',
            'question': f'Введите перевод слова: {card.term}',
            'correct': card.definition.lower().strip(),
            'card_id': card.pk,
            'hint': f'Начинается на "{card.definition[0]}..."' if card.definition else '',
        }