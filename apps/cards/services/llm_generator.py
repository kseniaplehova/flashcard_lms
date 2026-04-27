import json
import logging
import random
from typing import Dict, Any, List, Optional
from openai import OpenAI
from django.conf import settings
from apps.cards.models import AIGenerationLog, Flashcard
from apps.accounts.models import User

logger = logging.getLogger(__name__)


class LLMGeneratorService:
    def __init__(self):
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("API ключ не настроен")

        self.client = OpenAI(api_key=api_key, base_url=settings.OPENAI_BASE_URL)
        self.model = settings.OPENAI_MODEL

    def generate_example_sentence(
        self,
        term: str,
        definition: str,
        part_of_speech: str,
        target_language: str,
        user: Optional[User] = None,
        flashcard: Optional[Flashcard] = None,
    ) -> Dict[str, Any]:
        """
        Генерирует пример использования слова через ИИ.
        """
        system_prompt = (
            "You are a creative language tutor. "
            "Generate a natural, contextual example sentence that demonstrates "
            "the meaning and usage of the given word."
        )

        user_prompt = (
            f"Word: {term}\n"
            f"Part of speech: {part_of_speech or 'unknown'}\n"
            f"Definition: {definition or term}\n"
            f"Language: {target_language}\n\n"
            "Generate ONE natural example sentence. Return ONLY the sentence."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
                max_tokens=100,
            )

            example = response.choices[0].message.content
            if not example:
                example = f"This is a sample sentence with '{term}'."

            example = example.strip().strip('"').strip("'")
            tokens = response.usage.total_tokens if response.usage else 0

            self._log_generation(user_prompt, example, True, tokens)

            return {
                "example": example,
                "tokens_used": tokens,
            }

        except Exception as e:
            logger.error(f"Generate example error: {e}")
            return {
                "example": f"This is a sample sentence with '{term}'.",
                "tokens_used": 0,
                "error": str(e),
            }

    def generate_exercise(
        self,
        card: Flashcard,
        exercise_type: str = "auto",
        all_cards: Optional[List[Flashcard]] = None,
    ) -> Dict[str, Any]:
        """
        Генерирует разнообразные упражнения для карточки.
        """
        # Типы упражнений с весами (сложные чаще)
        exercise_types = [
            "multiple_choice",  # 1
            "typing",  # 2
            "reverse_typing",  # 3
            "fill_blank",  # 4
            "audio_guess",  # 5 - новое: угадать слово по описанию
            "synonym_match",  # 6 - новое: подобрать синоним из списка
            "sentence_build",  # 7 - новое: составить предложение
        ]

        if exercise_type == "auto":
            # Сложные упражнения имеют приоритет при повторении
            if all_cards and len(all_cards) > 3:
                weights = [1, 2, 2, 3, 3, 2, 3]  # веса для каждого типа
                exercise_type = random.choices(exercise_types, weights=weights, k=1)[0]
            else:
                exercise_type = random.choice(exercise_types[:4])  # только простые

        generators = {
            "multiple_choice": self._generate_multiple_choice,
            "typing": self._generate_typing,
            "reverse_typing": self._generate_reverse_typing,
            "fill_blank": self._generate_fill_blank,
            "audio_guess": self._generate_audio_guess,
            "synonym_match": self._generate_synonym_match,
            "sentence_build": self._generate_sentence_build,
        }

        generator = generators.get(exercise_type, self._generate_multiple_choice)

        # Некоторые генераторы не принимают all_cards
        if exercise_type in [
            "fill_blank",
            "typing",
            "reverse_typing",
            "audio_guess",
            "sentence_build",
        ]:
            return generator(card)
        else:
            return generator(card, all_cards or [])

    def _generate_audio_guess(
        self, card: Flashcard, all_cards: Optional[List[Flashcard]] = None
    ) -> Dict[str, Any]:
        """Угадать слово по определению (без вариантов)."""
        return {
            "type": "typing",
            "question": "Угадайте слово по определению:",
            "term": card.definition,
            "correct": card.term.lower().strip(),
            "card_id": card.pk,
            "hint": f"Первая буква: {card.term[0]}..." if card.term else "",
        }

    def _generate_synonym_match(
        self, card: Flashcard, all_cards: Optional[List[Flashcard]] = None
    ) -> Dict[str, Any]:
        """Подобрать синоним из 4 вариантов."""
        synonyms_map = {
            "happy": ["glad", "sad", "angry", "tired"],
            "big": ["large", "small", "tiny", "fast"],
            "fast": ["quick", "slow", "heavy", "light"],
            "smart": ["intelligent", "stupid", "lazy", "weak"],
            "beautiful": ["pretty", "ugly", "plain", "dull"],
            "delicious": ["tasty", "bitter", "sour", "salty"],
            "cold": ["chilly", "hot", "warm", "mild"],
        }

        options = synonyms_map.get(
            card.term.lower(),
            [
                f"синоним к {card.term}",
                f"антоним к {card.term}",
                f"похожее слово",
                f"противоположное",
            ],
        )
        random.shuffle(options)

        return {
            "type": "multiple_choice",
            "question": f'Выберите синоним к слову "{card.term}":',
            "term": card.term,
            "options": options,
            "correct": options[0] if card.term.lower() in synonyms_map else options[0],
            "card_id": card.pk,
        }

    def _generate_sentence_build(
        self, card: Flashcard, all_cards: Optional[List[Flashcard]] = None
    ) -> Dict[str, Any]:
        """Составить предложение из слов."""
        if card.example_sentence:
            words = card.example_sentence.split()
            if len(words) >= 4:
                correct = card.example_sentence
                shuffled = words[:]
                random.shuffle(shuffled)
                return {
                    "type": "typing",
                    "question": f'Составьте предложение из слов: {", ".join(shuffled)}',
                    "term": ", ".join(shuffled),
                    "correct": correct.lower().strip(),
                    "card_id": card.pk,
                    "hint": f"Используется слово: {card.term}",
                }

        # Fallback
        return self._generate_typing(card)

    def _generate_multiple_choice(
        self, card: Flashcard, all_cards: List[Flashcard]
    ) -> Dict[str, Any]:
        """Выбор правильного перевода из 4 вариантов."""
        correct = card.definition

        other_cards = [c for c in all_cards if c.pk != card.pk]
        if len(other_cards) >= 3:
            wrong_answers = random.sample([c.definition for c in other_cards], 3)
        else:
            wrong_answers = [
                f"Антоним к {card.term}",
                f"Синоним, но не точный",
                f"Созвучное слово",
            ]

        options = wrong_answers + [correct]
        random.shuffle(options)

        return {
            "type": "multiple_choice",
            "question": "🎯 Выберите правильный перевод:",
            "term": card.term,
            "options": options,
            "correct": correct,
            "card_id": card.pk,
        }

    def _generate_typing(
        self, card: Flashcard, all_cards: Optional[List[Flashcard]] = None
    ) -> Dict[str, Any]:
        """Ввод перевода с клавиатуры."""
        return {
            "type": "typing",
            "question": "⌨️ Введите перевод слова:",
            "term": card.term,
            "correct": card.definition.lower().strip(),
            "card_id": card.pk,
            "hint": (
                f"💡 Первая буква: {card.definition[0]}..." if card.definition else ""
            ),
        }

    def _generate_reverse_typing(
        self, card: Flashcard, all_cards: Optional[List[Flashcard]] = None
    ) -> Dict[str, Any]:
        """Обратный перевод (с русского на английский)."""
        return {
            "type": "reverse_typing",
            "question": "🔄 Как будет на изучаемом языке?",
            "definition": card.definition,
            "correct": card.term.lower().strip(),
            "card_id": card.pk,
            "hint": f"💡 Первая буква: {card.term[0]}..." if card.term else "",
        }

    def _generate_fill_blank(
        self, card: Flashcard, all_cards: Optional[List[Flashcard]] = None
    ) -> Dict[str, Any]:
        """Заполнить пропуск в предложении."""
        if card.example_sentence and card.term in card.example_sentence:
            sentence = card.example_sentence.replace(card.term, "_____", 1)
        else:
            sentences = [
                f"I really like _____. It's amazing!",
                f"Can you pass me the _____ please?",
                f"_____ is my favorite thing ever!",
                f"I don't understand what _____ means.",
            ]
            sentence = random.choice(sentences)

        return {
            "type": "fill_blank",
            "question": "📝 Заполните пропуск в предложении:",
            "sentence": sentence,
            "correct": card.term.lower().strip(),
            "card_id": card.pk,
        }

    def _generate_true_false(
        self, card: Flashcard, all_cards: List[Flashcard]
    ) -> Dict[str, Any]:
        """Правда или ложь: соответствует ли перевод слову."""
        is_correct = random.choice([True, False])

        if is_correct:
            shown_definition = card.definition
            correct_answer = "true"
        else:
            other_cards = [c for c in all_cards if c.pk != card.pk]
            if other_cards:
                wrong_card = random.choice(other_cards)
                shown_definition = wrong_card.definition
            else:
                shown_definition = f"Неправильный перевод"
            correct_answer = "false"

        return {
            "type": "true_false",
            "question": "❓ Верно ли, что это правильный перевод?",
            "term": card.term,
            "shown_definition": shown_definition,
            "correct": correct_answer,
            "card_id": card.pk,
        }

    def _generate_match_synonym(self, card: Flashcard) -> Dict[str, Any]:
        """Подобрать синоним к слову."""
        synonyms = {
            "happy": "glad",
            "big": "large",
            "small": "tiny",
            "fast": "quick",
            "smart": "intelligent",
            "beautiful": "pretty",
            "angry": "mad",
            "tired": "exhausted",
            "delicious": "tasty",
            "cold": "chilly",
        }

        synonym = synonyms.get(card.term.lower(), f"similar to {card.term}")

        options = [synonym, card.term, f"not {card.term}", f"opposite of {card.term}"]
        random.shuffle(options)

        return {
            "type": "multiple_choice",
            "question": f'🔤 Выберите синоним к слову "{card.term}":',
            "term": card.term,
            "options": options,
            "correct": synonym,
            "card_id": card.pk,
        }

    def _generate_word_scramble(self, card: Flashcard) -> Dict[str, Any]:
        """Собрать слово из перемешанных букв."""
        letters = list(card.term)
        random.shuffle(letters)
        scrambled = "".join(letters)

        while scrambled == card.term and len(card.term) > 2:
            random.shuffle(letters)
            scrambled = "".join(letters)

        return {
            "type": "typing",
            "question": f'🧩 Соберите слово из букв: "{scrambled}"',
            "term": scrambled,
            "correct": card.term.lower().strip(),
            "card_id": card.pk,
            "hint": f"💡 Перевод: {card.definition}",
        }

    def _generate_wrong_answers_ai(
        self, term: str, correct: str, count: int = 3
    ) -> List[str]:
        """Генерирует неправильные варианты ответов."""
        return [
            f"Не {correct}",
            f"Антоним к {term}",
            f"Похоже на {term}",
        ]

    def generate_cards_by_topic(
        self,
        topic: str,
        count: int = 10,
        target_lang: str = "en",
        native_lang: str = "ru",
    ) -> List[Dict[str, Any]]:
        """
        Генерирует список карточек по заданной теме.
        """
        system_prompt = (
            f"You are an expert language teacher. "
            f"Generate EXACTLY {count} vocabulary words about the topic '{topic}'. "
            f"ONLY words about '{topic}', nothing unrelated. "
            f"For each word, provide: the word in {target_lang}, "
            f"translation in {native_lang}. "
            "Return ONLY a valid JSON object with a 'words' array. "
            'Example: {"words": [{"term": "apple", "translation": "яблоко"}]}'
        )

        user_prompt = (
            f"Topic: {topic}\n"
            f"Number of words: {count}\n"
            f"IMPORTANT: Generate ONLY words about '{topic}'. No unrelated words."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=2000,
            )

            raw_content = response.choices[0].message.content
            print(f"DEBUG API RAW RESPONSE: {raw_content}")

            if not raw_content:
                raise ValueError("API вернул пустой ответ")

            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0]
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].split("```")[0]

            raw_content = raw_content.strip()

            data = json.loads(raw_content)
            cards = data.get("words", [])

            if not cards:
                if isinstance(data, list):
                    cards = data
                elif "cards" in data:
                    cards = data["cards"]

            print(f"DEBUG PARSED CARDS: {len(cards)} cards")

            tokens = response.usage.total_tokens if response.usage else 0
            self._log_generation(topic, raw_content, True, tokens)

            result = []
            for card in cards[:count]:
                term = card.get("term") or card.get("word") or ""
                translation = card.get("translation") or card.get("meaning") or ""

                if not term or not translation:
                    continue

                result.append(
                    {
                        "term": term.strip(),
                        "translation": translation.strip(),
                        "part_of_speech": card.get("part_of_speech", ""),
                        "example": card.get("example", ""),
                        "tokens_used": tokens // len(cards) if cards else 0,
                    }
                )

            # Если результат меньше запрошенного, возвращаем что есть (без fallback)
            print(f"DEBUG FINAL RESULT: {len(result)} cards")
            return result

        except Exception as e:
            logger.error(f"AI Error: {e}")
            self._log_generation(topic, str(e), False)
            # Возвращаем пустой список вместо fallback-карточек
            return []

    def _generate_fallback_cards(self, topic: str, count: int) -> List[Dict[str, Any]]:
        """Создает тестовые карточки, если API не сработал."""
        words = {
            "еда": ["apple", "bread", "cheese", "chicken", "fish"],
            "машина": ["car", "engine", "wheel", "door", "window"],
            "путешествия": ["hotel", "airport", "ticket", "passport", "luggage"],
        }

        topic_lower = topic.lower()
        base_words = words.get(
            topic_lower, ["word1", "word2", "word3", "word4", "word5"]
        )

        result = []
        for i in range(min(count, 10)):
            word = base_words[i % len(base_words)]
            result.append(
                {
                    "term": f"{word}_{i+1}" if i >= len(base_words) else word,
                    "translation": f"Перевод: {word}",
                    "part_of_speech": "noun",
                    "example": f"Example with {word}.",
                    "tokens_used": 0,
                }
            )

        print(f"DEBUG FALLBACK: generated {len(result)} cards")
        return result

    def _log_generation(
        self,
        prompt: str,
        response: str,
        success: bool,
        tokens: int = 0,
        user: Optional[User] = None,
        flashcard: Optional[Flashcard] = None,
    ):
        try:
            log_data = {
                "request_prompt": str(prompt)[:500],
                "response_content": str(response)[:1000],
                "was_successful": success,
                "tokens_used": tokens,
                "model_used": self.model,
            }
            if user:
                log_data["user"] = user
            if flashcard:
                log_data["flashcard"] = flashcard
            AIGenerationLog.objects.create(**log_data)
        except Exception:
            pass


LLMGenerator = LLMGeneratorService
