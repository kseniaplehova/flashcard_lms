from typing import Any
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Model


class OwnerRequiredMixin(UserPassesTestMixin):
    """Доступ только владельцу объекта."""
    
    def test_func(self) -> bool:
        obj = self.get_object()  # type: ignore[attr-defined]
        user = self.request.user  # type: ignore[attr-defined]
        return obj.owner == user  # type: ignore[attr-defined]


class StaffRequiredMixin(UserPassesTestMixin):
    """Доступ только персоналу (администратору)."""
    
    def test_func(self) -> bool:
        user = self.request.user  # type: ignore[attr-defined]
        return user.is_staff or user.is_superuser


class DeckAccessMixin(UserPassesTestMixin):
    """Проверка доступа к колоде: владелец, админ, или публичная."""
    
    def test_func(self) -> bool:
        deck = self.get_object()  # type: ignore[attr-defined]
        user = self.request.user  # type: ignore[attr-defined]
        return (
            deck.owner == user or  # type: ignore[attr-defined]
            user.is_staff or 
            getattr(deck, 'is_public', False) or 
            getattr(deck, 'visibility', 'private') == 'public'
        )


class OwnerOrStaffMixin(UserPassesTestMixin):
    """Доступ владельцу или администратору."""
    
    def test_func(self) -> bool:
        obj = self.get_object()  # type: ignore[attr-defined]
        user = self.request.user  # type: ignore[attr-defined]
        return obj.owner == user or user.is_staff  # type: ignore[attr-defined]