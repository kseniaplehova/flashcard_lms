import json
from typing import Dict, Any, Optional, List
from openai import OpenAI
from django.conf import settings
from apps.cards.models import Flashcard, AIGenerationLog
from apps.accounts.models import User


class LLMGeneratorService:
    """
    Сервис для взаимодействия с LLM API (OpenAI / DeepSeek).
    """
    
    def __init__(self):
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("API ключ не настроен в .env файле")
        
        # Инициализация с поддержкой кастомного base_url
        if hasattr(settings, 'OPENAI_BASE_URL') and settings.OPENAI_BASE_URL:
            self.client = OpenAI(
                api_key=api_key,
                base_url=settings.OPENAI_BASE_URL
            )
        else:
            self.client = OpenAI(api_key=api_key)
        
        self.model = settings.OPENAI_MODEL

    def generate_cards_by_topic(
        self,
        topic: str,
        count: int = 10,
        target_lang: str = "en",
        native_lang: str = "ru"
    ) -> List[Dict[str, Any]]:
        """
        Генерирует список карточек по заданной теме.
        """
        system_prompt = (
            f"You are an expert language teacher. "
            f"Generate {count} vocabulary words related to the topic '{topic}'. "
            f"For each word, provide: the word in {target_lang}, "
            f"translation in {native_lang}, part of speech, and an example sentence in {target_lang}. "
            "Return ONLY a valid JSON object with a 'words' array."
        )
        
        user_prompt = (
            f"Topic: {topic}\n"
            f"Number of words: {count}\n"
            f"Return format: {{\"words\": [{{\"term\": \"word\", \"translation\": \"translation\", "
            f"\"part_of_speech\": \"noun\", \"example\": \"example sentence\"}}]}}"
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8,
                max_tokens=2000
            )
            
            raw_content = response.choices[0].message.content
            if not raw_content:
                raise ValueError("API вернул пустой ответ")
            
            # Пробуем распарсить JSON
            try:
                data = json.loads(raw_content)
                cards = data.get('words', [])
            except json.JSONDecodeError:
                # Если ответ не в JSON, извлекаем слова из текста
                cards = self._extract_cards_from_text(raw_content, topic, count)
            
            tokens = response.usage.total_tokens if response.usage else 0
            
            self._log_generation(
                prompt=user_prompt,
                response=raw_content,
                success=True,
                tokens=tokens
            )
            
            return [
                {
                    'term': card.get('term', f'{topic}_{i}'),
                    'translation': card.get('translation', ''),
                    'part_of_speech': card.get('part_of_speech', 'noun'),
                    'example': card.get('example', ''),
                    'tokens_used': tokens // len(cards) if cards else 0
                }
                for i, card in enumerate(cards)
            ]
            
        except Exception as e:
            self._log_generation(
                prompt=user_prompt,
                response=str(e),
                success=False
            )
            raise

    def _extract_cards_from_text(self, text: str, topic: str, count: int) -> List[Dict]:
        """Извлекает карточки из текстового ответа."""
        cards = []
        lines = text.strip().split('\n')
        
        for i, line in enumerate(lines[:count]):
            parts = line.split(' - ')
            if len(parts) >= 2:
                cards.append({
                    'term': parts[0].strip(),
                    'translation': parts[1].strip(),
                    'part_of_speech': 'noun',
                    'example': f"This is an example with {parts[0].strip()}."
                })
        
        # Если не удалось извлечь, создаем заглушки
        if not cards:
            for i in range(count):
                cards.append({
                    'term': f'{topic}_word_{i+1}',
                    'translation': f'Перевод слова {i+1}',
                    'part_of_speech': 'noun',
                    'example': f'Example sentence with {topic}_word_{i+1}.'
                })
        
        return cards

    def generate_card_content(
        self, 
        term: str, 
        target_lang: str = "en", 
        native_lang: str = "ru"
    ) -> Dict[str, Any]:
        """Генерирует перевод, часть речи и пример для одного термина."""
        system_prompt = (
            f"You are an expert linguist. "
            f"Provide translation in {native_lang}, part of speech, and example in {target_lang}. "
            "Return ONLY a valid JSON object."
        )
        
        user_prompt = (
            f"Word: {term}\n"
            "Format: {\"translation\": \"...\", \"part_of_speech\": \"...\", \"example\": \"...\"}"
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            raw_content = response.choices[0].message.content
            if not raw_content:
                raise ValueError("API вернул пустой ответ")
            
            try:
                content = json.loads(raw_content)
            except json.JSONDecodeError:
                content = {
                    'translation': f'Перевод: {term}',
                    'part_of_speech': 'noun',
                    'example': f'This is an example with {term}.'
                }
            
            tokens = response.usage.total_tokens if response.usage else 0
            
            self._log_generation(
                prompt=user_prompt,
                response=raw_content,
                success=True,
                tokens=tokens
            )
            
            return {
                'translation': content.get('translation', ''),
                'part_of_speech': content.get('part_of_speech', ''),
                'example': content.get('example', ''),
                'tokens_used': tokens
            }
            
        except Exception as e:
            self._log_generation(
                prompt=user_prompt,
                response=str(e),
                success=False
            )
            return {
                'error': str(e),
                'translation': term,
                'part_of_speech': '',
                'example': '',
                'tokens_used': 0
            }

    def generate_example_sentence(
        self,
        term: str,
        definition: str,
        part_of_speech: str,
        target_language: str,
        user: Optional[User] = None,
        flashcard: Optional[Flashcard] = None,
    ) -> Dict[str, Any]:
        """Генерирует пример использования слова."""
        user_prompt = (
            f"Generate ONE natural example sentence using '{term}' ({part_of_speech}). "
            f"Definition: {definition}. Language: {target_language}. Return ONLY the sentence."
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a language tutor."},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8,
                max_tokens=100
            )
            
            example = response.choices[0].message.content
            if not example:
                example = f"This is a sample sentence with '{term}'."
            
            example = example.strip().strip('"').strip("'")
            tokens = response.usage.total_tokens if response.usage else 0
            
            self._log_generation(
                prompt=user_prompt,
                response=example,
                success=True,
                tokens=tokens,
                user=user,
                flashcard=flashcard
            )
            
            return {
                'example': example,
                'tokens_used': tokens,
            }
            
        except Exception as e:
            self._log_generation(
                prompt=user_prompt,
                response=str(e),
                success=False,
                user=user,
                flashcard=flashcard
            )
            return {
                'example': f"This is a sample sentence with '{term}'.",
                'tokens_used': 0,
                'error': str(e)
            }

    def _log_generation(
        self, 
        prompt: str, 
        response: str, 
        success: bool, 
        tokens: int = 0,
        user: Optional[User] = None,
        flashcard: Optional[Flashcard] = None
    ):
        """Сохранение истории запросов."""
        try:
            log_data = {
                'request_prompt': prompt[:500],
                'response_content': response[:1000],
                'was_successful': success,
                'tokens_used': tokens,
                'model_used': self.model,
            }
            
            if user:
                log_data['user'] = user
            if flashcard:
                log_data['flashcard'] = flashcard
                
            AIGenerationLog.objects.create(**log_data)
        except Exception:
            pass


LLMGenerator = LLMGeneratorService