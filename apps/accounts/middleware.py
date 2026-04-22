from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from apps.accounts.models import UserActivity


class UserActivityMiddleware(MiddlewareMixin):
    """
    Отслеживает активность пользователей.
    """
    
    def process_request(self, request):
        if request.user.is_authenticated:
            # Логируем вход только раз в сессию
            session_key = f'activity_logged_{request.user.pk}'
            if session_key not in request.session:
                UserActivity.objects.create(
                    user=request.user,
                    action='login',
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
                )
                request.session[session_key] = True
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip