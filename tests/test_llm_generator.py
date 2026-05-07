import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

import json
from django.test import TestCase
from unittest.mock import patch, MagicMock

from apps.cards.services.llm_generator import LLMGeneratorService
from apps.cards.models import AIGenerationLog


class LLMGeneratorServiceTestCase(TestCase):
    """Тестирование сервиса генерации контента через LLM"""
    
    def setUp(self):
        # Мокаем settings
        self.settings_patcher = patch('apps.cards.services.llm_generator.settings')
        self.mock_settings = self.settings_patcher.start()
        self.mock_settings.OPENAI_API_KEY = 'test-key'
        self.mock_settings.OPENAI_BASE_URL = 'https://api.test.com'
        self.mock_settings.OPENAI_MODEL = 'test-model'
        
        self.service = LLMGeneratorService()
    
    def tearDown(self):
        self.settings_patcher.stop()
        AIGenerationLog.objects.all().delete()
    
    @patch.object(LLMGeneratorService, '_log_generation')
    def test_successful_generation(self, mock_log):
        """Тест успешной генерации карточек"""
        valid_response = {
            "words": [
                {"term": "correr", "translation": "бежать", "part_of_speech": "глагол"},
                {"term": "caminar", "translation": "ходить", "part_of_speech": "глагол"},
            ]
        }
        
        with patch.object(self.service.client.chat.completions, 'create') as mock_create:
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content=json.dumps(valid_response)))
            ]
            mock_response.usage = MagicMock(total_tokens=100)
            mock_create.return_value = mock_response
            
            result = self.service.generate_cards_by_topic(
                topic="испанские глаголы",
                target_lang="es",
                native_lang="ru",
                count=2
            )
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['term'], 'correr')
            self.assertIn('translation', result[0])
    
    @patch.object(LLMGeneratorService, '_log_generation')
    def test_invalid_json_returns_empty(self, mock_log):
        """Тест: некорректный JSON возвращает пустой список"""
        with patch.object(self.service.client.chat.completions, 'create') as mock_create:
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="Это не JSON"))
            ]
            mock_create.return_value = mock_response
            
            result = self.service.generate_cards_by_topic(
                topic="test", target_lang="en", native_lang="ru", count=5
            )
            
            self.assertEqual(result, [])
    
    @patch.object(LLMGeneratorService, '_log_generation')
    def test_empty_api_response(self, mock_log):
        """Тест: пустой ответ API"""
        with patch.object(self.service.client.chat.completions, 'create') as mock_create:
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content=None))
            ]
            mock_create.return_value = mock_response
            
            result = self.service.generate_cards_by_topic(
                topic="test", target_lang="en", native_lang="ru", count=5
            )
            
            self.assertEqual(result, [])
    
    @patch.object(LLMGeneratorService, '_log_generation')
    def test_generate_example_sentence(self, mock_log):
        """Тест генерации примера предложения"""
        with patch.object(self.service.client.chat.completions, 'create') as mock_create:
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="This is a test example."))
            ]
            mock_response.usage = MagicMock(total_tokens=50)
            mock_create.return_value = mock_response
            
            result = self.service.generate_example_sentence(
                term="test",
                definition="тест",
                part_of_speech="noun",
                target_language="en"
            )
            
            self.assertIn('example', result)
            self.assertEqual(result['example'], 'This is a test example.')
    
    def test_log_generation(self):
        """Тест создания лога генерации"""
        self.service._log_generation(
            prompt="test prompt",
            response="test response",
            success=True,
            tokens=50
        )
        
        log = AIGenerationLog.objects.first()
        self.assertIsNotNone(log)
        self.assertTrue(log.was_successful)
        self.assertEqual(log.tokens_used, 50)