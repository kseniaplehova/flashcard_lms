import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cards.models import Deck, Flashcard

User = get_user_model()


class StudySessionTestCase(TestCase):
    """Тестирование учебной сессии"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='student',
            password='study123'
        )
        
        self.deck = Deck.objects.create(
            name='Test Deck',
            owner=self.user,
            target_language='en',
            native_language='ru'
        )
        
        self.cards = []
        for term, definition in [
            ('hello', 'привет'), ('goodbye', 'пока'),
            ('book', 'книга'), ('cat', 'кот'), ('dog', 'собака')
        ]:
            self.cards.append(Flashcard.objects.create(
                deck=self.deck, term=term, definition=definition, part_of_speech='noun'
            ))
    
    def test_start_study_session(self):
        """Тест: начало учебной сессии"""
        self.client.login(username='student', password='study123')
        url = reverse('cards:study_session', args=[self.deck.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('card', response.context)
    
    def test_answer_correct_flashcard(self):
        """Тест: правильный ответ"""
        self.client.login(username='student', password='study123')
        url = reverse('cards:study_session', args=[self.deck.pk])
        
        response = self.client.get(url)
        card = response.context['card']
        
        self.client.post(url, {'card_id': str(card.pk), 'is_correct': 'true'})
        
        session = self.client.session
        key = f'study_session_{self.deck.pk}_completed'
        self.assertIn(card.pk, session.get(key, []))
    
    def test_answer_incorrect_flashcard(self):
        """Тест: неправильный ответ"""
        self.client.login(username='student', password='study123')
        url = reverse('cards:study_session', args=[self.deck.pk])
        
        response = self.client.get(url)
        card = response.context['card']
        
        self.client.post(url, {'card_id': str(card.pk), 'is_correct': 'false'})
        
        session = self.client.session
        key = f'study_session_{self.deck.pk}_struggling'
        self.assertIn(card.pk, session.get(key, []))
    
    def test_all_correct_no_struggling(self):
        """Тест: все правильно → нет struggling"""
        self.client.login(username='student', password='study123')
        url = reverse('cards:study_session', args=[self.deck.pk])
        
        self.client.get(url)
        
        for card in self.cards:
            self.client.post(url, {'card_id': str(card.pk), 'is_correct': 'true'})
        
        session = self.client.session
        key = f'study_session_{self.deck.pk}_struggling'
        self.assertEqual(len(session.get(key, [])), 0)
    
    def test_some_incorrect(self):
        """Тест: часть неправильных"""
        self.client.login(username='student', password='study123')
        url = reverse('cards:study_session', args=[self.deck.pk])
        
        self.client.get(url)
        
        for i, card in enumerate(self.cards):
            is_correct = 'false' if i < 2 else 'true'
            self.client.post(url, {'card_id': str(card.pk), 'is_correct': is_correct})
        
        session = self.client.session
        key = f'study_session_{self.deck.pk}_struggling'
        self.assertEqual(len(session.get(key, [])), 2)
    
    def test_study_results_page(self):
        """Тест: страница результатов"""
        user2 = User.objects.create_user(username='s2', password='p2')
        client2 = Client()
        client2.login(username='s2', password='p2')
        
        deck2 = Deck.objects.create(owner=user2, name='D2', target_language='en', native_language='ru')
        c1 = Flashcard.objects.create(deck=deck2, term='a', definition='1')
        c2 = Flashcard.objects.create(deck=deck2, term='b', definition='2')
        
        session = client2.session
        session[f'study_session_{deck2.pk}_test_results'] = {
            str(c1.pk): {'term': 'a', 'definition': '1', 'correct': True},
            str(c2.pk): {'term': 'b', 'definition': '2', 'correct': False},
        }
        session.save()
        
        response = client2.get(reverse('cards:study_results', args=[deck2.pk]))
        self.assertEqual(response.status_code, 200)
    
    def test_requires_login(self):
        """Тест: без логина → редирект"""
        url = reverse('cards:study_session', args=[self.deck.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
    
    def tearDown(self):
        Flashcard.objects.all().delete()
        Deck.objects.all().delete()
        User.objects.all().delete()