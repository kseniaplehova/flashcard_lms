from .base import *
import os

DEBUG = False
ALLOWED_HOSTS = ["kseniaplehova.pythonanywhere.com", "localhost", "127.0.0.1"]

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-fallback-for-production")

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# OpenAI settings
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "llama-3.3-70b-versatile")

# Database - исправлено
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 30,
        },
    }
}

# Static files
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_URL = "/static/"
