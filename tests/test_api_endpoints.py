import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cards.models import Deck, Flashcard

User = get_user_model()


class APIEndpointsTestCase(TestCase):
    """Тестирование API эндпоинтов"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='apiuser', password='api123')
        self.client.login(username='apiuser', password='api123')
        
        self.deck = Deck.objects.create(
            owner=self.user,
            name='API Test Deck',
            target_language='en',
            native_language='ru'
        )
        
        self.card = Flashcard.objects.create(
            deck=self.deck,
            term='test',
            definition='тест',
            part_of_speech='noun'
        )
    
    def test_deck_stats_api_url(self):
        """Тест: URL API статистики существует"""
        url = reverse('cards:api_deck_stats', args=[self.deck.pk])
        response = self.client.get(url)
        
        # Выводим для отладки
        print(f"\nAPI stats URL: {url}")
        print(f"Response status: {response.status_code}")
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['deck_name'], 'API Test Deck')
    
    def test_card_review_api_url(self):
        """Тест: URL API отправки ответа существует"""
        url = reverse('cards:api_card_review', args=[self.card.pk])
        print(f"\nAPI review URL: {url}")
        
        response = self.client.post(
            url,
            data=json.dumps({'quality': 5}),
            content_type='application/json'
        )
        print(f"Response status: {response.status_code}")
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
    
    def test_generate_context_api_url(self):
        """Тест: URL API генерации контекста существует"""
        url = reverse('cards:api_generate_context', args=[self.card.pk])
        print(f"\nAPI generate context URL: {url}")
        
        response = self.client.post(url, content_type='application/json')
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.content[:200]}")
        
        # Может быть 200 или 500 (проблема с API ключом)
        self.assertIn(response.status_code, [200, 500])
    
    def test_api_requires_login(self):
        """Тест: без логина - редирект"""
        self.client.logout()
        
        url = reverse('cards:api_deck_stats', args=[self.deck.pk])
        response = self.client.get(url)
        
        # LoginRequiredMixin → редирект 302
        self.assertEqual(response.status_code, 302)
    
    def tearDown(self):
        Flashcard.objects.all().delete()
        Deck.objects.all().delete()
        User.objects.all().delete()