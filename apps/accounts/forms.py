from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User


from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import RegexValidator
from .models import User


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=False)

    password1 = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput,
        min_length=8,
        help_text="Минимум 8 символов. Можно использовать буквы, цифры или вместе.",
    )
    password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput,
        help_text="Повторите пароль.",
    )

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]


class ProfileEditForm(forms.ModelForm):
    """
    Форма редактирования профиля.
    SQL: UPDATE users SET username=?, email=?, first_name=?, last_name=? WHERE id=?
    """

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name"]
