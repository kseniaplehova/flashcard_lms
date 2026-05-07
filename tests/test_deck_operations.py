import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch, MagicMock

from apps.cards.models import Deck, Flashcard
from apps.cards.services.llm_generator import LLMGeneratorService

User = get_user_model()


class DeckOperationsTestCase(TestCase):
    """Тестирование операций с колодами и карточками"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='deckuser',
            password='deck123'
        )
        self.client.login(username='deckuser', password='deck123')
    
    def test_create_deck(self):
        """Тест создания колоды"""
        response = self.client.post(reverse('cards:deck_create'), {
            'name': 'New Test Deck',
            'description': 'Test description',
            'target_language': 'en',
            'native_language': 'ru',
            'visibility': 'private',
        })
        
        self.assertEqual(response.status_code, 302)  # Редирект после создания
        
        deck = Deck.objects.get(name='New Test Deck')
        self.assertEqual(deck.owner, self.user)
        self.assertEqual(deck.target_language, 'en')
    
    def test_create_manual_card(self):
        """Тест ручного создания карточки"""
        deck = Deck.objects.create(
            name='Manual Deck',
            owner=self.user,
            target_language='en',
            native_language='ru'
        )
        
        with patch.object(LLMGeneratorService, 'generate_example_sentence') as mock_gen:
            mock_gen.return_value = {'example': 'This is a test example.', 'tokens_used': 0}
            
            url = reverse('cards:card_create', args=[deck.pk])
            response = self.client.post(url, {'term': 'test_word'})
            
            self.assertEqual(response.status_code, 302)
            
            card = Flashcard.objects.get(term='test_word', deck=deck)
            self.assertIsNotNone(card)
            self.assertEqual(card.example_sentence, 'This is a test example.')
    
    @patch.object(LLMGeneratorService, 'generate_cards_by_topic')
    def test_bulk_create_cards(self, mock_generate):
        """Тест массовой генерации карточек через ИИ"""
        mock_generate.return_value = [
            {'term': 'word1', 'translation': 'слово1', 'part_of_speech': 'noun', 'example': 'Example 1'},
            {'term': 'word2', 'translation': 'слово2', 'part_of_speech': 'noun', 'example': 'Example 2'},
            {'term': 'word3', 'translation': 'слово3', 'part_of_speech': 'verb', 'example': 'Example 3'},
        ]
        
        deck = Deck.objects.create(
            name='AI Deck',
            owner=self.user,
            target_language='en',
            native_language='ru'
        )
        
        url = reverse('cards:card_bulk_create', args=[deck.pk])
        response = self.client.post(url, {
            'topic': 'testing',
            'count': 3
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Проверяем, что карточки созданы
        cards_count = Flashcard.objects.filter(deck=deck, is_active=True).count()
        self.assertEqual(cards_count, 3)
    
    def test_delete_deck(self):
        """Тест удаления колоды"""
        deck = Deck.objects.create(
            name='To Delete',
            owner=self.user,
            target_language='en',
            native_language='ru'
        )
        
        url = reverse('cards:deck_delete', args=[deck.pk])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Deck.objects.filter(pk=deck.pk).exists())
    
    def test_copy_public_deck(self):
        """Тест копирования публичной колоды"""
        # Создаём другого пользователя с публичной колодой
        other_user = User.objects.create_user(username='other', password='other123')
        public_deck = Deck.objects.create(
            name='Public Deck',
            owner=other_user,
            visibility='public',
            target_language='es',
            native_language='ru'
        )
        
        # Добавляем карточки в публичную колоду
        Flashcard.objects.create(
            deck=public_deck,
            term='hola',
            definition='привет',
            part_of_speech='interjection'
        )
        
        url = reverse('cards:copy_deck', args=[public_deck.pk])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 302)
        
        # Проверяем, что копия создалась
        copied = Deck.objects.get(owner=self.user, name__startswith='Копия: Public Deck')
        self.assertIsNotNone(copied)
        self.assertEqual(copied.flashcard_set.count(), 1)
    
    def test_like_deck(self):
        """Тест лайка колоды"""
        other_user = User.objects.create_user(username='other2', password='other123')
        public_deck = Deck.objects.create(
            name='Likeable Deck',
            owner=other_user,
            visibility='public',
            target_language='fr',
            native_language='ru'
        )
        
        url = reverse('cards:toggle_like', args=[public_deck.pk])
        
        # Лайкаем
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        
        import json
        data = json.loads(response.content)
        self.assertTrue(data['liked'])
        
        # Проверяем в БД
        public_deck.refresh_from_db()
        self.assertIn(self.user, public_deck.likes.all())
    
    def tearDown(self):
        Flashcard.objects.all().delete()
        Deck.objects.all().delete()
        User.objects.all().delete()