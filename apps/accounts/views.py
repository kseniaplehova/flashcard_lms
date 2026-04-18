from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView
from apps.accounts.forms import UserRegistrationForm
from apps.accounts.models import User


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


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        if hasattr(user, 'decks'):
            context['decks_count'] = user.decks.count()  # type: ignore[attr-defined]
        else:
            context['decks_count'] = 0
        
        return context