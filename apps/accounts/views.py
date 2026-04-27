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
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from apps.accounts.models import User
from apps.accounts.forms import ProfileEditForm
from apps.cards.models import Deck, DeckProgress, UserCardProgress
from django.db.models import Sum


class ProfileView(LoginRequiredMixin, TemplateView):
    """Страница профиля пользователя со статистикой."""
    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Колоды пользователя
        context['total_decks'] = Deck.objects.filter(owner=user).count()
        context['public_decks'] = Deck.objects.filter(owner=user, visibility='public').count()
        
        # Статистика обучения
        progress = DeckProgress.objects.filter(user=user).aggregate(
            total_mastered=Sum('cards_mastered'),
            total_learning=Sum('cards_learning'),
            total_struggling=Sum('cards_struggling')
        )
        context['cards_mastered'] = progress['total_mastered'] or 0
        context['cards_learning'] = progress['total_learning'] or 0
        context['cards_struggling'] = progress['total_struggling'] or 0
        
        # Общее количество попыток
        context['total_attempts'] = UserCardProgress.objects.filter(
            user=user
        ).aggregate(total=Sum('total_attempts'))['total'] or 0
        
        # Последние колоды
        context['recent_decks'] = Deck.objects.filter(owner=user).order_by('-updated_at')[:5]
        
        # Прогресс по дням (последние 7 дней)
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        daily_progress = []
        for i in range(7):
            date = today - timedelta(days=i)
            count = UserCardProgress.objects.filter(
                user=user,
                last_reviewed_at__date=date
            ).count()
            daily_progress.append({'date': date.strftime('%d.%m'), 'count': count})
        context['daily_progress'] = list(reversed(daily_progress))
        
        return context


class ProfileEditView(LoginRequiredMixin, UpdateView):
    """Редактирование профиля."""
    model = User
    form_class = ProfileEditForm
    template_name = "accounts/profile_edit.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Профиль обновлен!")
        return super().form_valid(form)


class RegisterView(CreateView):
    model = User
    form_class = UserRegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("cards:dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.object  # type: ignore[attr-defined]
        login(self.request, user)
        return response


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Админ-панель со статистикой.
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

        # Общая статистика
        context["total_users"] = User.objects.count()
        context["active_today"] = (
            UserActivity.objects.filter(created_at__date=today)
            .values("user")
            .distinct()
            .count()
        )
        context["active_week"] = (
            UserActivity.objects.filter(created_at__gte=week_ago)
            .values("user")
            .distinct()
            .count()
        )
        context["total_decks"] = Deck.objects.count()
        context["public_decks"] = Deck.objects.filter(visibility="public").count()
        context["total_cards"] = Flashcard.objects.count()
        context["total_likes"] = Deck.objects.aggregate(total=Count("likes"))["total"]

        # Статистика по дням (последние 7 дней)
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

        # Статистика по языкам
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
            language_data.append(
                {
                    "code": lang["target_language"],
                    "name": self._get_language_name(lang["target_language"]),
                    "count": lang["count"],
                    "public_count": lang["public_count"],
                    "likes": lang["likes"],
                }
            )
        context["language_stats"] = language_data

        # Топ активных пользователей
        context["top_users"] = (
            UserActivity.objects.filter(created_at__gte=month_ago)
            .values("user__username")
            .annotate(activity_count=Count("id"))
            .order_by("-activity_count")[:10]
        )

        # Последние действия
        context["recent_activities"] = UserActivity.objects.select_related(
            "user", "deck"
        ).order_by("-created_at")[:20]

        # Популярные колоды
        context["popular_decks"] = Deck.objects.annotate(
            study_count=Count("user_progress"), likes_count=Count("likes")
        ).order_by("-study_count")[:10]

        # Новые пользователи по дням
        new_users_stats = []
        for i in range(7):
            date = today - timedelta(days=i)
            count = User.objects.filter(date_joined__date=date).count()
            new_users_stats.append({"date": date.strftime("%d.%m"), "count": count})
        context["new_users_stats"] = list(reversed(new_users_stats))

        return context

    def _get_language_name(self, code):
        names = {
            "en": "Английский",
            "es": "Испанский",
            "fr": "Французский",
            "de": "Немецкий",
            "it": "Итальянский",
            "pt": "Португальский",
            "ja": "Японский",
            "ko": "Корейский",
            "zh": "Китайский",
            "ru": "Русский",
        }
        return names.get(code, code.upper())
