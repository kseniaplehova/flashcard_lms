from .base import *

DEBUG = True
ALLOWED_HOSTS = ["kseniaplehova.pythonanywhere.com", "localhost", "127.0.0.1", "*"]

DATABASES["default"]["OPTIONS"].update(
    {
        "check_same_thread": False,
    }
)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
