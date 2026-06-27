import os
import tempfile
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent.parent / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
# Secure-by-default: DEBUG is off unless explicitly enabled (dev .env sets it on).
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "recipes",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Production serves hashed, compressed assets via WhiteNoise's manifest storage.
# Tests render templates with {% static %} but never run collectstatic, so the
# manifest does not exist — fall back to plain storage there (set in conftest).
_TESTING = os.environ.get("DJANGO_TESTING") == "1"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if _TESTING
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# External services
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://localhost:8001")
MAX_DURATION_SECONDS = int(os.environ.get("MAX_DURATION_SECONDS", "900"))

# Celery
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_EAGER", "false").lower() == "true"

# Auth redirects (used in Task 2)
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "discover"
LOGOUT_REDIRECT_URL = "login"

# Upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100 MB

# Directory where uploaded media is staged for the worker to read. Must point at
# a path shared between the web and worker containers (see docker-compose volume).
UPLOAD_DIR = os.environ.get(
    "UPLOAD_DIR", str(Path(tempfile.gettempdir()) / "recipe-web-uploads")
)

AUTH_USER_MODEL = "accounts.User"
