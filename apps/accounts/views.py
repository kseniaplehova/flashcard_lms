from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView
from apps.accounts.forms import UserRegistrationForm
from apps.accounts.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta
from apps.accounts.models import User, UserActivity
from apps.cards.models import Deck, Flashcard, UserCardProgress


class RegisterView(CreateView):
    model = User
    form_class = UserRegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('cards:dashboard')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.object  # type: ignore[attr-defined]
        login(self.request, user)
        return response

    
class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Админ-панель со статистикой.
    """
    template_name = 'accounts/admin_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # Общая статистика
        context['total_users'] = User.objects.count()
        context['active_today'] = UserActivity.objects.filter(
            created_at__date=today
        ).values('user').distinct().count()
        
        context['active_week'] = UserActivity.objects.filter(
            created_at__gte=week_ago
        ).values('user').distinct().count()
        
        # Статистика по дням (последние 7 дней)
        daily_stats = []
        for i in range(7):
            date = today - timedelta(days=i)
            count = UserActivity.objects.filter(
                created_at__date=date
            ).values('user').distinct().count()
            daily_stats.append({
                'date': date.strftime('%d.%m'),
                'count': count
            })
        context['daily_stats'] = list(reversed(daily_stats))
        
        # Статистика по колодам
        context['total_decks'] = Deck.objects.count()
        context['public_decks'] = Deck.objects.filter(visibility='public').count()
        context['total_cards'] = Flashcard.objects.count()
        
        # Топ активных пользователей
        context['top_users'] = UserActivity.objects.filter(
            created_at__gte=month_ago
        ).values('user__username').annotate(
            activity_count=Count('id')
        ).order_by('-activity_count')[:10]
        
        # Последние действия
        context['recent_activities'] = UserActivity.objects.select_related(
            'user', 'deck'
        ).order_by('-created_at')[:20]
        
        # Популярные колоды
        context['popular_decks'] = Deck.objects.annotate(
            study_count=Count('user_progress', filter=Q(user_progress__last_session_at__isnull=False))
        ).order_by('-study_count')[:5]
        
        return context