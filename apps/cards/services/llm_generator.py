import json
import logging
from typing import Dict, Any, List
from openai import OpenAI
from django.conf import settings
from apps.cards.models import AIGenerationLog

logger = logging.getLogger(__name__)

class LLMGeneratorService:
    def __init__(self):
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("API ключ ZenMux не настроен")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=settings.OPENAI_BASE_URL
        )
        self.model = settings.OPENAI_MODEL

    def generate_cards_by_topic(
        self,
        topic: str,
        count: int = 10,
        target_lang: str = "en",
        native_lang: str = "ru"
    ) -> List[Dict[str, Any]]:
        """
        Генерирует список карточек по заданной теме через ZenMux.
        """
        system_prompt = (
            f"You are an expert language teacher. "
            f"Generate {count} vocabulary words related to the topic '{topic}'. "
            f"For each word, provide: the word in {target_lang}, "
            f"translation in {native_lang}, part of speech, and an example sentence in {target_lang}. "
            "Return ONLY a valid JSON object with a 'words' array. "
            "Example: {\"words\": [{\"term\": \"apple\", \"translation\": \"яблоко\", "
            "\"part_of_speech\": \"noun\", \"example\": \"I eat an apple every day.\"}]}"
        )
        
        user_prompt = f"Topic: {topic}\nNumber of words: {count}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
                
            )
            
            raw_content = response.choices[0].message.content
            if not raw_content:
                raise ValueError("API вернул пустой ответ")

            # Очистка ответа от Markdown-разметки, если модель её добавила
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0]
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].split("```")[0]

            data = json.loads(raw_content.strip())
            cards = data.get('words', [])
            
            tokens = response.usage.total_tokens if response.usage else 0
            self._log_generation(topic, raw_content, True, tokens)
            
            # Возвращаем данные в формате, который ожидает view
            return [
                {
                    'term': card.get('term', ''),
                    'translation': card.get('translation', ''),
                    'part_of_speech': card.get('part_of_speech', 'noun'),
                    'example': card.get('example', ''),
                    'tokens_used': tokens // len(cards) if cards else 0
                }
                for card in cards[:count]
            ]
            
        except Exception as e:
            logger.error(f"ZenMux AI Error: {e}")
            self._log_generation(topic, str(e), False)
            raise

    def _log_generation(self, prompt: str, response: str, success: bool, tokens: int = 0):
        try:
            AIGenerationLog.objects.create(
                request_prompt=str(prompt)[:500],
                response_content=str(response)[:1000],
                was_successful=success,
                tokens_used=tokens,
                model_used=self.model
            )
        except Exception:
            pass

# ВНИМАНИЕ: Здесь была критическая ошибка. Убран вызов ().
LLMGenerator = LLMGeneratorService