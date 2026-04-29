from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView, UpdateView
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q, Sum
from datetime import timedelta

from apps.accounts.forms import UserRegistrationForm, ProfileEditForm
from apps.accounts.models import User, UserActivity
from apps.cards.models import Deck, Flashcard, DeckProgress, UserCardProgress


class RegisterView(CreateView):
    """
    Регистрация нового пользователя.
    SQL: INSERT INTO users (см. sql/init.sql, строка 2)
    """
    model = User
    form_class = UserRegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("cards:dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.object  # type: ignore[attr-defined]
        login(self.request, user)
        return response


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        context['total_decks'] = Deck.objects.filter(owner=user).count()
        context['public_decks'] = Deck.objects.filter(owner=user, visibility='public').count()
        
        progress = DeckProgress.objects.filter(user=user).aggregate(
            total_mastered=Sum('cards_mastered'),
            total_learning=Sum('cards_learning'),
            total_struggling=Sum('cards_struggling')
        )
        context['cards_mastered'] = progress['total_mastered'] or 0
        context['cards_learning'] = progress['total_learning'] or 0
        context['cards_struggling'] = progress['total_struggling'] or 0
        
        # Стрик (дни подряд)
        context['streak'] = user.current_streak
        
        context['recent_decks'] = Deck.objects.filter(owner=user).order_by('-updated_at')[:5]
        
        # Прогресс по дням (последние 7 дней)
        today = timezone.now().date()
        daily_progress = []
        for i in range(7):
            date = today - timedelta(days=i)
            count = UserActivity.objects.filter(
                user=user,
                created_at__date=date
            ).count()
            daily_progress.append({'date': date.strftime('%d.%m'), 'count': count})
        context['daily_progress'] = list(reversed(daily_progress))
        
        return context


class ProfileEditView(LoginRequiredMixin, UpdateView):
    """
    Редактирование профиля.
    SQL: UPDATE users SET ... WHERE id = ?
    """
    model = User
    form_class = ProfileEditForm
    template_name = "accounts/profile_edit.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Профиль обновлен!")
        return super().form_valid(form)


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Админ-панель со статистикой.
    SQL: sql/admin_queries.sql (все запросы)
    """

    template_name = "accounts/admin_dashboard.html"

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        # Общая статистика (sql/admin_queries.sql, строка 4)
        context["total_users"] = User.objects.count()
        # Активных сегодня (sql/admin_queries.sql, строка 10)
        context["active_today"] = (
            UserActivity.objects.filter(created_at__date=today)
            .values("user")
            .distinct()
            .count()
        )
        # Активных за неделю (sql/admin_queries.sql, строка 15)
        context["active_week"] = (
            UserActivity.objects.filter(created_at__gte=week_ago)
            .values("user")
            .distinct()
            .count()
        )
        context["total_decks"] = Deck.objects.count()
        context["public_decks"] = Deck.objects.filter(visibility="public").count()
        context["total_cards"] = Flashcard.objects.count()
        # Всего лайков (sql/admin_queries.sql, строка 8)
        context["total_likes"] = Deck.objects.aggregate(total=Count("likes"))["total"]

        # Статистика по дням (sql/admin_queries.sql, строка 20)
        daily_stats = []
        for i in range(7):
            date = today - timedelta(days=i)
            count = (
                UserActivity.objects.filter(created_at__date=date)
                .values("user")
                .distinct()
                .count()
            )
            daily_stats.append({"date": date.strftime("%d.%m"), "count": count})
        context["daily_stats"] = list(reversed(daily_stats))

        # Статистика по языкам (sql/admin_queries.sql, строка 30)
        lang_stats = (
            Deck.objects.values("target_language")
            .annotate(
                count=Count("id"),
                public_count=Count("id", filter=Q(visibility="public")),
                likes=Count("likes"),
            )
            .order_by("-count")
        )

        language_data = []
        for lang in lang_stats:
            language_data.append({
                "code": lang["target_language"],
                "name": self._get_language_name(lang["target_language"]),
                "count": lang["count"],
                "public_count": lang["public_count"],
                "likes": lang["likes"],
            })
        context["language_stats"] = language_data

        # Топ активных пользователей (sql/admin_queries.sql, строка 40)
        context["top_users"] = (
            UserActivity.objects.filter(created_at__gte=month_ago)
            .values("user__username")
            .annotate(activity_count=Count("id"))
            .order_by("-activity_count")[:10]
        )

        # Последние действия (sql/admin_queries.sql, строка 47)
        context["recent_activities"] = UserActivity.objects.select_related(
            "user", "deck"
        ).order_by("-created_at")[:20]

        # Популярные колоды (sql/admin_queries.sql, строка 55)
        context["popular_decks"] = Deck.objects.annotate(
            study_count=Count("user_progress"),
            likes_count=Count("likes")
        ).order_by("-study_count")[:10]

        # Новые пользователи по дням (sql/admin_queries.sql, строка 25)
        new_users_stats = []
        for i in range(7):
            date = today - timedelta(days=i)
            count = User.objects.filter(date_joined__date=date).count()
            new_users_stats.append({"date": date.strftime("%d.%m"), "count": count})
        context["new_users_stats"] = list(reversed(new_users_stats))

        return context

    def _get_language_name(self, code: str) -> str:
        """Возвращает название языка по коду."""
        names = {
            "en": "Английский", "es": "Испанский", "fr": "Французский",
            "de": "Немецкий", "it": "Итальянский", "pt": "Португальский",
            "ja": "Японский", "ko": "Корейский", "zh": "Китайский", "ru": "Русский",
        }
        return names.get(code, code.upper())