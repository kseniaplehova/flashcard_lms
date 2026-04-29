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

    # ========== ГЕНЕРАЦИЯ ПРИМЕРА ==========
    def generate_example_sentence(
        self, term: str, definition: str, part_of_speech: str,
        target_language: str, user=None, flashcard=None
    ) -> Dict[str, Any]:
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
                temperature=0.8, max_tokens=100,
            )
            example = response.choices[0].message.content or f"This is a sample sentence with '{term}'."
            example = example.strip().strip('"').strip("'")
            tokens = response.usage.total_tokens if response.usage else 0
            self._log_generation(user_prompt, example, True, tokens)
            return {"example": example, "tokens_used": tokens}
        except Exception as e:
            logger.error(f"Generate example error: {e}")
            return {"example": f"This is a sample sentence with '{term}'.", "tokens_used": 0, "error": str(e)}

    # ========== ГЕНЕРАЦИЯ КАРТОЧЕК ПО ТЕМЕ ==========
    def generate_cards_by_topic(
        self, topic: str, count: int = 10,
        target_lang: str = "en", native_lang: str = "ru"
    ) -> List[Dict[str, Any]]:
        non_latin = target_lang in ["zh", "ja", "ko", "ar", "he", "th"]
        lang_names = {
            "ja": "Japanese", "zh": "Chinese", "ko": "Korean",
            "ar": "Arabic", "he": "Hebrew", "th": "Thai",
            "en": "English", "ru": "Russian",
        }
        target_name = lang_names.get(target_lang, target_lang)
        native_name = lang_names.get(native_lang, native_lang)

        if non_latin:
            system_prompt = (
                f"You are a native {target_name} speaker. "
                f"Respond ONLY with a JSON object."
            )
            user_prompt = (
                f"Translate these {native_name} words to {target_name} "
                f"(use {target_name} characters, NOT romaji):\n"
                f"1. World\n2. Globe\n3. Planet\n4. Earth\n5. Nation\n"
                f"6. Society\n7. People\n8. Peace\n9. Harmony\n10. Unity\n\n"
                f"The topic is '{topic}'. Provide the translations in this JSON format:\n"
                f'{{"words": [{{"term": "世界", "translation": "мир"}}, {{"term": "地球", "translation": "земля"}}]}}'
            )
        else:
            system_prompt = (
                f"You are a professional {target_name} language teacher. "
                f"Respond ONLY with a JSON object."
            )
            user_prompt = (
                f"Create a list of {count} basic {target_name} words about the topic '{topic}'. "
                f"For each word, provide the word in {target_name} and its translation in {native_name}.\n\n"
                f"Respond in this exact JSON format:\n"
                f'{{"words": [{{"term": "word", "translation": "перевод"}}]}}'
            )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3, max_tokens=2000,
            )
            raw_content = response.choices[0].message.content
            print(f"DEBUG API RAW RESPONSE: {raw_content}")
            if not raw_content:
                raise ValueError("API вернул пустой ответ")

            json_str = raw_content.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]
            if "{" in json_str:
                json_str = json_str[json_str.index("{"):]
            if "}" in json_str:
                json_str = json_str[:json_str.rindex("}") + 1]

            data = json.loads(json_str)
            cards = data.get("words", [])
            if not cards and isinstance(data, list):
                cards = data
            print(f"DEBUG PARSED CARDS: {len(cards)} cards")

            tokens = response.usage.total_tokens if response.usage else 0
            self._log_generation(topic, json_str, True, tokens)

            result = []
            for card in cards[:count]:
                term = ""
                for key in ["term", "word", "original", "native", "target", "character"]:
                    val = card.get(key, "")
                    if val and str(val).strip():
                        term = str(val).strip()
                        break
                translation = ""
                for key in ["translation", "meaning", "definition", "translate"]:
                    val = card.get(key, "")
                    if val and str(val).strip():
                        translation = str(val).strip()
                        break
                if not term or not translation:
                    continue
                result.append({
                    "term": term, "translation": translation,
                    "part_of_speech": card.get("part_of_speech", ""),
                    "example": card.get("example", ""),
                    "tokens_used": 0,
                })
            print(f"DEBUG FINAL RESULT: {len(result)} cards")
            return result
        except Exception as e:
            logger.error(f"AI Error: {e}")
            return []

    # ========== ГЕНЕРАЦИЯ УПРАЖНЕНИЙ ==========
    def generate_exercise(
        self, card: Flashcard, exercise_type: str = "auto",
        all_cards: Optional[List[Flashcard]] = None
    ) -> Dict[str, Any]:
        if exercise_type == "flashcard":
            return self._generate_flashcard(card)

        test_types = [
            "multiple_choice", "typing", "reverse_typing",
            "fill_blank", "synonym_match", "sentence_build"
        ]
        if exercise_type == "auto":
            exercise_type = random.choice(test_types)

        generators = {
            "multiple_choice": self._generate_multiple_choice,
            "typing": self._generate_typing,
            "reverse_typing": self._generate_reverse_typing,
            "fill_blank": self._generate_fill_blank,
            "synonym_match": self._generate_synonym_match,
            "sentence_build": self._generate_sentence_build,
        }
        gen = generators.get(exercise_type, self._generate_multiple_choice)
        if exercise_type in ("fill_blank", "typing", "reverse_typing", "sentence_build"):
            return gen(card)
        else:
            return gen(card, all_cards or [])

    def _generate_flashcard(self, card: Flashcard) -> Dict[str, Any]:
        return {"type": "flashcard", "term": card.term, "definition": card.definition, "card_id": card.pk}

    # ---------- СИНОНИМЫ ЧЕРЕЗ ИИ ----------
    def _generate_synonyms_ai(self, term: str, all_cards: List[Flashcard]) -> Optional[Dict[str, Any]]:
        available_words = [c.definition for c in all_cards[:10] if c.term != term]
        system = (
            "You are a language teacher creating a synonym exercise. "
            "Return ONLY a JSON object: "
            '{"synonym": "correct_synonym", "wrong_options": ["wrong1","wrong2","wrong3"]}. '
            "The original word MUST NOT appear in the options."
        )
        user = (
            f"Word: {term}\n"
            f"Context (other words): {', '.join(available_words[:5])}\n\n"
            "Provide a real synonym and three plausible but incorrect options."
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.7, max_tokens=200
            )
            data = json.loads(resp.choices[0].message.content)
            syn = data.get("synonym", "").strip()
            wrong = data.get("wrong_options", [])
            if syn and len(wrong) >= 3:
                return {"synonym": syn, "wrong_options": wrong[:3]}
        except Exception as e:
            logger.warning(f"Synonym AI failed: {e}")
        return None

    def _generate_synonym_match(self, card: Flashcard, all_cards: List[Flashcard]) -> Dict[str, Any]:
        ai_result = self._generate_synonyms_ai(card.term, all_cards)
        if ai_result:
            options = ai_result["wrong_options"] + [ai_result["synonym"]]
            random.shuffle(options)
            return {
                "type": "multiple_choice",
                "question": f'🔤 Выберите синоним к слову "{card.term}":',
                "term": card.term, "options": options,
                "correct": ai_result["synonym"], "card_id": card.pk,
            }
        return self._generate_multiple_choice(card, all_cards)

    # ---------- FILL BLANK ЧЕРЕЗ ИИ ----------
    def _generate_fill_blank_ai(self, term: str, definition: str) -> Optional[str]:
        system = (
            "You are a language teacher. Create a natural sentence where the word is missing. "
            "Represent the missing word as '_______'. Return ONLY the sentence."
        )
        user = f"Word: {term}\nDefinition: {definition}\nMake a sentence with a blank for this word."
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.8, max_tokens=60
            )
            sentence = resp.choices[0].message.content.strip()
            if "_______" not in sentence:
                sentence = sentence.replace(term, "_______", 1)
            return sentence
        except Exception as e:
            logger.warning(f"Fill blank AI failed: {e}")
            return None

    def _generate_fill_blank(self, card: Flashcard, *args) -> Dict[str, Any]:
        ai_sentence = self._generate_fill_blank_ai(card.term, card.definition)
        if ai_sentence:
            sentence = ai_sentence
        elif card.example_sentence and card.term in card.example_sentence:
            sentence = card.example_sentence.replace(card.term, "_______", 1)
        else:
            sentence = f"I really like _______. It's amazing!"
        return {
            "type": "fill_blank",
            "question": "📝 Вставьте пропущенное слово:",
            "sentence": sentence,
            "correct": card.term.lower().strip(),
            "card_id": card.pk,
        }

    # ---------- ОСТАЛЬНЫЕ ГЕНЕРАТОРЫ ----------
    def _generate_multiple_choice(self, card: Flashcard, all_cards: List[Flashcard]) -> Dict[str, Any]:
        correct = card.definition
        other_cards = [c for c in all_cards if c.pk != card.pk]
        
        # Собираем УНИКАЛЬНЫЕ переводы (исключая правильный)
        other_definitions = []
        for c in other_cards:
            if c.definition.lower() != correct.lower():  # исключаем дубликаты правильного
                other_definitions.append(c.definition)
        
        # Убираем дубликаты
        unique_definitions = list(set(other_definitions))
        
        if len(unique_definitions) >= 3:
            wrong_answers = random.sample(unique_definitions, 3)
        else:
            # Добиваем непохожими вариантами
            wrong_answers = unique_definitions.copy()
            while len(wrong_answers) < 3:
                fake = f"Не {correct}" if len(wrong_answers) == 0 else f"Антоним к {card.term}" if len(wrong_answers) == 1 else f"Созвучное слово"
                if fake not in wrong_answers:
                    wrong_answers.append(fake)
        
        options = wrong_answers + [correct]
        random.shuffle(options)
        
        return {
            "type": "multiple_choice",
            "question": "🎯 Выберите правильный перевод:",
            "term": card.term, "options": options,
            "correct": correct, "card_id": card.pk,
        }

    def _generate_typing(self, card: Flashcard, *args) -> Dict[str, Any]:
        return {
            "type": "typing", "question": "⌨️ Введите перевод слова:",
            "term": card.term, "correct": card.definition.lower().strip(),
            "card_id": card.pk,
            "hint": f"💡 Первая буква: {card.definition[0]}..." if card.definition else "",
        }

    def _generate_reverse_typing(self, card: Flashcard, *args) -> Dict[str, Any]:
        return {
            "type": "reverse_typing", "question": "🔄 Как будет на изучаемом языке?",
            "definition": card.definition, "correct": card.term.lower().strip(),
            "card_id": card.pk,
            "hint": f"💡 Первая буква: {card.term[0]}..." if card.term else "",
        }

    def _generate_sentence_build(self, card: Flashcard, *args) -> Dict[str, Any]:
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
        return self._generate_typing(card)

    def _generate_true_false(self, card: Flashcard, all_cards: List[Flashcard]) -> Dict[str, Any]:
        is_correct = random.choice([True, False])
        if is_correct:
            shown_definition, correct_answer = card.definition, "true"
        else:
            other = [c for c in all_cards if c.pk != card.pk]
            shown_definition = random.choice(other).definition if other else "Неправильный перевод"
            correct_answer = "false"
        return {
            "type": "true_false", "question": "❓ Верно ли, что это правильный перевод?",
            "term": card.term, "shown_definition": shown_definition,
            "correct": correct_answer, "card_id": card.pk,
        }

    def _generate_word_scramble(self, card: Flashcard) -> Dict[str, Any]:
        letters = list(card.term)
        random.shuffle(letters)
        scrambled = "".join(letters)
        while scrambled == card.term and len(card.term) > 2:
            random.shuffle(letters)
            scrambled = "".join(letters)
        return {
            "type": "typing", "question": f'🧩 Соберите слово из букв: "{scrambled}"',
            "term": scrambled, "correct": card.term.lower().strip(),
            "card_id": card.pk, "hint": f"💡 Перевод: {card.definition}",
        }

    # ---------- FALLBACK И ЛОГИ ----------
    def _generate_fallback_cards(self, topic: str, count: int) -> List[Dict[str, Any]]:
        words = {
            "еда": ["apple", "bread", "cheese", "chicken", "fish"],
            "машина": ["car", "engine", "wheel", "door", "window"],
            "путешествия": ["hotel", "airport", "ticket", "passport", "luggage"],
        }
        base_words = words.get(topic.lower(), ["word1", "word2", "word3", "word4", "word5"])
        result = []
        for i in range(min(count, 10)):
            word = base_words[i % len(base_words)]
            result.append({
                "term": f"{word}_{i+1}" if i >= len(base_words) else word,
                "translation": f"Перевод: {word}",
                "part_of_speech": "noun",
                "example": f"Example with {word}.",
                "tokens_used": 0,
            })
        return result

    def _log_generation(self, prompt: str, response: str, success: bool,
                        tokens: int = 0, user=None, flashcard=None):
        try:
            AIGenerationLog.objects.create(
                request_prompt=str(prompt)[:500],
                response_content=str(response)[:1000],
                was_successful=success, tokens_used=tokens,
                model_used=self.model, user=user, flashcard=flashcard,
            )
        except Exception:
            pass


LLMGenerator = LLMGeneratorService