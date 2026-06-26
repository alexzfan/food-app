# Recipe Finder Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Expo mobile app with a Django + HTMX web app that searches YouTube cooking videos, transcribes a user-uploaded audio file, extracts a structured recipe via a local/hosted LLM, and saves/searches/favorites recipes.

**Architecture:** A Django app (`apps/web`) owns auth, CRUD, YouTube search, uploads, and orchestration; it renders server-side HTML with HTMX. A FastAPI ML service (`apps/audio-service`, repurposed) owns Whisper transcription of uploaded files and a pluggable recipe extractor (local Gemma 3n default, hosted API fallback). Postgres stores data; Redis backs Celery, which runs the slow transcribe→extract job while HTMX polls status.

**Tech Stack:** Python 3.11, Django 5, HTMX, Alpine.js, Celery + Redis, Postgres, FastAPI, faster-whisper, httpx, pytest / pytest-django, Docker Compose.

## Global Constraints

- Python version: 3.11 (matches existing `apps/audio-service` Dockerfile).
- No server-side YouTube downloading. `yt-dlp` is removed entirely; ingestion is upload/paste only.
- Recipe JSON shape is fixed (matches the mobile `RecipeSummary`):
  `ingredients: [{name, amount, unit?, notes?}]`, `instructions: [{step, text, duration?}]`,
  plus `title, description, tags[], cuisine?, cook_time_minutes?, prep_time_minutes?, servings?, difficulty(easy|medium|hard)`.
- Max uploaded media duration guard: `MAX_DURATION_SECONDS` (default 900), reused from the existing service.
- YouTube search appends `" recipe"` to the query, `type=video`, `videoDuration=medium`, `relevanceLanguage=en` (preserve existing behavior).
- Auth scope v1: Django email/password sessions only. No OAuth, no email verification.
- All new Python code is formatted with `ruff`/`black` defaults; tests use `pytest`.
- Tests must not load real ML models (Whisper/Gemma) — always stub/mock them.
- Django tests run on SQLite (`DATABASE_URL` unset); production/dev uses Postgres via `DATABASE_URL`.

---

### Task 1: Django project skeleton, settings, health check

**Files:**
- Create: `apps/web/requirements.txt`
- Create: `apps/web/manage.py`
- Create: `apps/web/config/__init__.py`
- Create: `apps/web/config/settings.py`
- Create: `apps/web/config/urls.py`
- Create: `apps/web/config/wsgi.py`
- Create: `apps/web/core/__init__.py`
- Create: `apps/web/core/apps.py`
- Create: `apps/web/core/views.py`
- Create: `apps/web/pytest.ini`
- Create: `apps/web/conftest.py`
- Test: `apps/web/core/tests/test_health.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a runnable Django project rooted at `apps/web`; settings module `config.settings`; a `GET /health/` view returning `{"status": "ok"}`; pytest configured with `DJANGO_SETTINGS_MODULE=config.settings`.

- [ ] **Step 1: Create `apps/web/requirements.txt`**

```
Django==5.0.6
dj-database-url==2.1.0
psycopg[binary]==3.1.18
gunicorn==22.0.0
celery==5.3.6
redis==5.0.4
httpx==0.26.0
python-dotenv==1.0.1
pytest==8.2.0
pytest-django==4.8.0
```

- [ ] **Step 2: Create `apps/web/manage.py`**

```python
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create `apps/web/config/__init__.py`, `config/wsgi.py`, `core/__init__.py`**

`config/__init__.py`: empty file.

`config/wsgi.py`:
```python
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
```

`core/__init__.py`: empty file.

- [ ] **Step 4: Create `apps/web/config/settings.py`**

```python
import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent.parent / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
```

- [ ] **Step 5: Create `apps/web/core/apps.py` and `core/views.py`**

`core/apps.py`:
```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
```

`core/views.py`:
```python
from django.http import JsonResponse


def health(request):
    return JsonResponse({"status": "ok"})
```

- [ ] **Step 6: Create `apps/web/config/urls.py`**

```python
from django.contrib import admin
from django.urls import path

from core.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
]
```

- [ ] **Step 7: Create `apps/web/pytest.ini` and `conftest.py`**

`pytest.ini`:
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = test_*.py
```

`conftest.py`:
```python
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
```

- [ ] **Step 8: Write the failing test `apps/web/core/tests/test_health.py`**

Also create empty `apps/web/core/tests/__init__.py`.

```python
import pytest


@pytest.mark.django_db
def test_health_returns_ok(client):
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 9: Run test to verify it fails**

Run: `cd apps/web && python -m pytest core/tests/test_health.py -v`
Expected: collection succeeds, test fails only if wiring is wrong; with all files present it should PASS. If imports fail, fix paths. (Run `pip install -r requirements.txt` first.)

- [ ] **Step 10: Run test to verify it passes**

Run: `cd apps/web && python -m pytest core/tests/test_health.py -v`
Expected: PASS (1 passed).

- [ ] **Step 11: Commit**

```bash
git add apps/web
git commit -m "feat(web): scaffold Django project with health check"
```

---

### Task 2: Email/password auth (custom user, signup/login/logout)

**Files:**
- Create: `apps/web/accounts/__init__.py`
- Create: `apps/web/accounts/apps.py`
- Create: `apps/web/accounts/models.py`
- Create: `apps/web/accounts/managers.py`
- Create: `apps/web/accounts/forms.py`
- Create: `apps/web/accounts/views.py`
- Create: `apps/web/accounts/urls.py`
- Create: `apps/web/templates/base.html`
- Create: `apps/web/templates/accounts/login.html`
- Create: `apps/web/templates/accounts/signup.html`
- Modify: `apps/web/config/settings.py` (add `accounts` to INSTALLED_APPS, set `AUTH_USER_MODEL`)
- Modify: `apps/web/config/urls.py` (include accounts urls)
- Test: `apps/web/accounts/tests/test_auth.py`

**Interfaces:**
- Consumes: project skeleton from Task 1.
- Produces: `AUTH_USER_MODEL = "accounts.User"` with `email` as `USERNAME_FIELD` and a `display_name` field; named URLs `login`, `logout`, `signup`; a `base.html` template other pages extend (blocks `title`, `content`, nav showing auth state).

- [ ] **Step 1: Create custom user model and manager**

`apps/web/accounts/managers.py`:
```python
from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create(email, password, **extra)
```

`apps/web/accounts/models.py`:
```python
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=150, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email
```

`apps/web/accounts/apps.py`:
```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
```

- [ ] **Step 2: Wire settings**

In `config/settings.py` add `"accounts"` to `INSTALLED_APPS` (before `"core"`) and add at the end:
```python
AUTH_USER_MODEL = "accounts.User"
```

- [ ] **Step 3: Create forms and views**

`apps/web/accounts/forms.py`:
```python
from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class SignupForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)

    class Meta:
        model = User
        fields = ["email", "display_name"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
```

`apps/web/accounts/views.py`:
```python
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

from .forms import SignupForm


class AppLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class AppLogoutView(LogoutView):
    pass


def signup(request):
    if request.user.is_authenticated:
        return redirect("discover")
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("discover")
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form})
```

- [ ] **Step 4: Create urls**

`apps/web/accounts/urls.py`:
```python
from django.urls import path

from .views import AppLoginView, AppLogoutView, signup

urlpatterns = [
    path("login/", AppLoginView.as_view(), name="login"),
    path("logout/", AppLogoutView.as_view(), name="logout"),
    path("signup/", signup, name="signup"),
]
```

In `config/urls.py` add `from django.urls import include` and `path("", include("accounts.urls")),`.

- [ ] **Step 5: Create templates**

`apps/web/templates/base.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Recipe Finder{% endblock %}</title>
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>
</head>
<body>
  <nav>
    <a href="{% url 'discover' %}">Discover</a>
    {% if user.is_authenticated %}
      <a href="{% url 'saved' %}">Saved</a>
      <a href="{% url 'favorites' %}">Favorites</a>
      <a href="{% url 'profile' %}">Profile</a>
      <form method="post" action="{% url 'logout' %}" style="display:inline">
        {% csrf_token %}<button type="submit">Log out</button>
      </form>
    {% else %}
      <a href="{% url 'login' %}">Log in</a>
      <a href="{% url 'signup' %}">Sign up</a>
    {% endif %}
  </nav>
  {% if messages %}<ul>{% for m in messages %}<li>{{ m }}</li>{% endfor %}</ul>{% endif %}
  <main>{% block content %}{% endblock %}</main>
</body>
</html>
```

`apps/web/templates/accounts/login.html`:
```html
{% extends "base.html" %}
{% block title %}Log in{% endblock %}
{% block content %}
<h1>Log in</h1>
<form method="post">{% csrf_token %}{{ form.as_p }}<button type="submit">Log in</button></form>
<a href="{% url 'signup' %}">Need an account? Sign up</a>
{% endblock %}
```

`apps/web/templates/accounts/signup.html`:
```html
{% extends "base.html" %}
{% block title %}Sign up{% endblock %}
{% block content %}
<h1>Sign up</h1>
<form method="post">{% csrf_token %}{{ form.as_p }}<button type="submit">Sign up</button></form>
<a href="{% url 'login' %}">Already have an account? Log in</a>
{% endblock %}
```

> Note: `discover`, `saved`, `favorites`, `profile` URLs are defined in later tasks. The auth tests in this task do not render `base.html` nav with those links resolved; they post to `signup`/`login` directly. Add a temporary placeholder `path("", ...)` only if a test needs `discover` — instead, tests assert redirects to `/` without following them.

- [ ] **Step 6: Write the failing tests**

Create `apps/web/accounts/tests/__init__.py` (empty) and `apps/web/accounts/tests/test_auth.py`:
```python
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_signup_creates_user_and_logs_in(client):
    resp = client.post(
        "/signup/",
        {"email": "cook@example.com", "display_name": "Cook", "password": "supersecret"},
    )
    assert resp.status_code == 302
    user = User.objects.get(email="cook@example.com")
    assert user.check_password("supersecret")
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
def test_login_with_email(client):
    User.objects.create_user(email="a@b.com", password="supersecret")
    resp = client.post("/login/", {"username": "a@b.com", "password": "supersecret"})
    assert resp.status_code == 302
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
def test_email_must_be_unique(client):
    User.objects.create_user(email="a@b.com", password="supersecret")
    form_resp = client.post(
        "/signup/", {"email": "a@b.com", "display_name": "x", "password": "supersecret"}
    )
    assert form_resp.status_code == 200  # re-render with error
    assert User.objects.filter(email="a@b.com").count() == 1
```

- [ ] **Step 7: Make migrations and run tests to verify they fail then pass**

Run: `cd apps/web && python manage.py makemigrations accounts && python -m pytest accounts/tests/test_auth.py -v`
Expected: 3 passed. (Django's `LoginView` uses field name `username` which maps to `USERNAME_FIELD=email`.)

- [ ] **Step 8: Commit**

```bash
git add apps/web
git commit -m "feat(web): email/password auth with custom user model"
```

---

### Task 3: Recipe, Favorite, ExtractionJob models

**Files:**
- Create: `apps/web/recipes/__init__.py`
- Create: `apps/web/recipes/apps.py`
- Create: `apps/web/recipes/models.py`
- Create: `apps/web/recipes/admin.py`
- Modify: `apps/web/config/settings.py` (add `recipes` to INSTALLED_APPS)
- Test: `apps/web/recipes/tests/test_models.py`

**Interfaces:**
- Consumes: `accounts.User`.
- Produces: models `Recipe`, `Favorite`, `ExtractionJob` with these fields/choices, used by all later tasks:
  - `Recipe(owner FK, youtube_video_id CharField blank, title, description, thumbnail_url, channel_name, ingredients JSON, instructions JSON, tags JSON, cuisine, cook_time_minutes, prep_time_minutes, servings, difficulty, created_at, updated_at)`
  - `Favorite(user FK, recipe FK, created_at)` unique_together(user, recipe)
  - `ExtractionJob(owner FK, status, step_label, source, youtube_video_id, title, error, recipe FK nullable, created_at, updated_at)` with `Status` choices `QUEUED, TRANSCRIBING, EXTRACTING, DONE, FAILED` and `Source` choices `UPLOAD, PASTE_TRANSCRIPT, PASTE_TEXT`.

- [ ] **Step 1: Create models**

`apps/web/recipes/models.py`:
```python
from django.conf import settings
from django.db import models


class Recipe(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "easy"
        MEDIUM = "medium"
        HARD = "hard"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipes"
    )
    youtube_video_id = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    channel_name = models.CharField(max_length=255, blank=True)
    ingredients = models.JSONField(default=list)   # [{name, amount, unit?, notes?}]
    instructions = models.JSONField(default=list)  # [{step, text, duration?}]
    tags = models.JSONField(default=list)          # [str]
    cuisine = models.CharField(max_length=100, blank=True)
    cook_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    prep_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    servings = models.PositiveIntegerField(null=True, blank=True)
    difficulty = models.CharField(
        max_length=10, choices=Difficulty.choices, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, related_name="favorited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "recipe")


class ExtractionJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        TRANSCRIBING = "transcribing"
        EXTRACTING = "extracting"
        DONE = "done"
        FAILED = "failed"

    class Source(models.TextChoices):
        UPLOAD = "upload"
        PASTE_TRANSCRIPT = "paste_transcript"
        PASTE_TEXT = "paste_text"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jobs"
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED
    )
    step_label = models.CharField(max_length=64, blank=True)
    source = models.CharField(max_length=20, choices=Source.choices)
    youtube_video_id = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=255, blank=True)
    error = models.TextField(blank=True)
    recipe = models.ForeignKey(
        Recipe, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
```

`apps/web/recipes/apps.py`:
```python
from django.apps import AppConfig


class RecipesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "recipes"
```

`apps/web/recipes/admin.py`:
```python
from django.contrib import admin

from .models import ExtractionJob, Favorite, Recipe

admin.site.register(Recipe)
admin.site.register(Favorite)
admin.site.register(ExtractionJob)
```

- [ ] **Step 2: Wire settings**

Add `"recipes"` to `INSTALLED_APPS` in `config/settings.py`.

- [ ] **Step 3: Write the failing tests**

Create `apps/web/recipes/tests/__init__.py` (empty) and `apps/web/recipes/tests/test_models.py`:
```python
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from recipes.models import ExtractionJob, Favorite, Recipe

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@e.com", password="supersecret")


def test_recipe_defaults(user):
    r = Recipe.objects.create(owner=user, title="Pasta")
    assert r.ingredients == []
    assert r.instructions == []
    assert r.tags == []
    assert r.youtube_video_id == ""


def test_favorite_unique_per_user_recipe(user):
    r = Recipe.objects.create(owner=user, title="Pasta")
    Favorite.objects.create(user=user, recipe=r)
    with pytest.raises(IntegrityError):
        Favorite.objects.create(user=user, recipe=r)


def test_extraction_job_starts_queued(user):
    job = ExtractionJob.objects.create(owner=user, source=ExtractionJob.Source.UPLOAD)
    assert job.status == ExtractionJob.Status.QUEUED
    assert job.recipe is None
```

- [ ] **Step 4: Make migrations, run tests**

Run: `cd apps/web && python manage.py makemigrations recipes && python -m pytest recipes/tests/test_models.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "feat(web): recipe, favorite, and extraction-job models"
```

---

### Task 4: YouTube search service + Discover page

**Files:**
- Create: `apps/web/recipes/youtube.py`
- Create: `apps/web/recipes/views.py`
- Create: `apps/web/recipes/urls.py`
- Create: `apps/web/templates/recipes/discover.html`
- Create: `apps/web/templates/recipes/_results.html`
- Modify: `apps/web/config/urls.py` (include recipes urls)
- Test: `apps/web/recipes/tests/test_youtube.py`
- Test: `apps/web/recipes/tests/test_discover.py`

**Interfaces:**
- Consumes: `settings.YOUTUBE_API_KEY`.
- Produces: `youtube.search_recipe_videos(query, max_results=10, page_token=None) -> dict` returning `{"videos": [ {id,title,description,thumbnail_url,channel_title,channel_id} ], "next_page_token": str|None}`; named URLs `discover` (GET page) and `youtube_search` (GET, HTMX, returns `_results.html` partial).

- [ ] **Step 1: Port the YouTube search service**

`apps/web/recipes/youtube.py`:
```python
import httpx
from django.conf import settings

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def search_recipe_videos(query, max_results=10, page_token=None):
    params = {
        "part": "snippet",
        "q": f"{query} recipe",
        "type": "video",
        "maxResults": str(max_results),
        "key": settings.YOUTUBE_API_KEY,
        "videoDuration": "medium",
        "relevanceLanguage": "en",
    }
    if page_token:
        params["pageToken"] = page_token

    resp = httpx.get(f"{YOUTUBE_API_BASE}/search", params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    videos = []
    for item in data.get("items", []):
        snip = item["snippet"]
        videos.append(
            {
                "id": item["id"]["videoId"],
                "title": snip["title"],
                "description": snip.get("description", ""),
                "thumbnail_url": snip["thumbnails"]["high"]["url"],
                "channel_title": snip["channelTitle"],
                "channel_id": snip["channelId"],
            }
        )
    return {"videos": videos, "next_page_token": data.get("nextPageToken")}
```

- [ ] **Step 2: Write the failing service test**

`apps/web/recipes/tests/test_youtube.py`:
```python
from unittest.mock import patch

from recipes import youtube


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_search_maps_fields():
    payload = {
        "items": [
            {
                "id": {"videoId": "abc123"},
                "snippet": {
                    "title": "Best Pasta",
                    "description": "yum",
                    "thumbnails": {"high": {"url": "http://img/x.jpg"}},
                    "channelTitle": "Chef",
                    "channelId": "ch1",
                },
            }
        ],
        "nextPageToken": "NEXT",
    }
    with patch("recipes.youtube.httpx.get", return_value=FakeResp(payload)) as g:
        result = youtube.search_recipe_videos("pasta")
    assert result["videos"][0] == {
        "id": "abc123",
        "title": "Best Pasta",
        "description": "yum",
        "thumbnail_url": "http://img/x.jpg",
        "channel_title": "Chef",
        "channel_id": "ch1",
    }
    assert result["next_page_token"] == "NEXT"
    # query gets " recipe" appended
    assert g.call_args.kwargs["params"]["q"] == "pasta recipe"
```

- [ ] **Step 3: Run service test to verify pass**

Run: `cd apps/web && python -m pytest recipes/tests/test_youtube.py -v`
Expected: 1 passed.

- [ ] **Step 4: Create Discover views**

`apps/web/recipes/views.py`:
```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from . import youtube


@login_required
def discover(request):
    return render(request, "recipes/discover.html")


@login_required
def youtube_search(request):
    query = request.GET.get("q", "").strip()
    videos = []
    error = None
    if query:
        try:
            videos = youtube.search_recipe_videos(query)["videos"]
        except Exception:
            error = "Search failed. Try again."
    return render(
        request, "recipes/_results.html", {"videos": videos, "error": error, "query": query}
    )
```

- [ ] **Step 5: Create recipes urls and wire**

`apps/web/recipes/urls.py`:
```python
from django.urls import path

from . import views

urlpatterns = [
    path("", views.discover, name="discover"),
    path("youtube/search/", views.youtube_search, name="youtube_search"),
]
```

In `config/urls.py` add `path("", include("recipes.urls")),` AFTER the accounts include (so `accounts` `login` etc. resolve; `discover` is at `""`).

- [ ] **Step 6: Create templates**

`apps/web/templates/recipes/discover.html`:
```html
{% extends "base.html" %}
{% block title %}Discover{% endblock %}
{% block content %}
<h1>Discover recipes</h1>
<input type="search" name="q" placeholder="Search YouTube for recipes..."
       hx-get="{% url 'youtube_search' %}" hx-target="#results"
       hx-trigger="keyup changed delay:500ms, search">
<div id="results"></div>
{% endblock %}
```

`apps/web/templates/recipes/_results.html`:
```html
{% if error %}<p>{{ error }}</p>{% endif %}
{% for v in videos %}
<div class="video-card" x-data="{ open: false }">
  <img src="{{ v.thumbnail_url }}" alt="" width="240">
  <h3>{{ v.title }}</h3>
  <p>{{ v.channel_title }}</p>
  <button @click="open = !open">Use this video</button>
  <div x-show="open">
    <iframe width="320" height="180"
            src="https://www.youtube.com/embed/{{ v.id }}"
            frameborder="0" allowfullscreen></iframe>
    {% include "recipes/_ingest_panel.html" with video=v %}
  </div>
</div>
{% empty %}
{% if query %}<p>No videos found.</p>{% endif %}
{% endfor %}
```

> Note: `_ingest_panel.html` is created in Task 8. To keep this task's tests green, create a placeholder `apps/web/templates/recipes/_ingest_panel.html` containing a single comment `{# ingest panel added in Task 8 #}` now; Task 8 replaces its contents.

- [ ] **Step 7: Write the failing Discover tests**

`apps/web/recipes/tests/test_discover.py`:
```python
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def auth_client(client, db):
    User.objects.create_user(email="u@e.com", password="supersecret")
    client.login(username="u@e.com", password="supersecret")
    return client


def test_discover_requires_login(client, db):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login/" in resp["Location"]


def test_discover_renders_for_user(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 200
    assert b"Discover recipes" in resp.content


def test_youtube_search_renders_results(auth_client):
    fake = {"videos": [{"id": "abc", "title": "Pasta", "description": "",
                        "thumbnail_url": "http://i/x.jpg", "channel_title": "Chef",
                        "channel_id": "c"}], "next_page_token": None}
    with patch("recipes.views.youtube.search_recipe_videos", return_value=fake):
        resp = auth_client.get("/youtube/search/", {"q": "pasta"})
    assert resp.status_code == 200
    assert b"Pasta" in resp.content
    assert b"youtube.com/embed/abc" in resp.content
```

- [ ] **Step 8: Run tests to verify pass**

Run: `cd apps/web && python -m pytest recipes/tests/ -v`
Expected: all passed.

- [ ] **Step 9: Commit**

```bash
git add apps/web
git commit -m "feat(web): youtube search service and discover page with embed"
```

---

### Task 5: FastAPI ML service — transcription of uploaded files

**Files:**
- Modify (rewrite): `apps/audio-service/app/main.py`
- Create: `apps/audio-service/app/transcription.py`
- Modify: `apps/audio-service/requirements.txt` (remove `yt-dlp`, add `python-multipart` stays, add nothing for whisper)
- Create: `apps/audio-service/tests/__init__.py`
- Test: `apps/audio-service/tests/test_transcribe.py`

**Interfaces:**
- Consumes: nothing from Django.
- Produces: FastAPI app with `POST /transcribe` (multipart form field `file`) returning `{"transcript": str, "language": str, "duration": float}`; `GET /health`; a `transcribe_file(path) -> dict` function in `transcription.py` that wraps Whisper and is the unit under test (mockable).

- [ ] **Step 1: Update requirements**

Rewrite `apps/audio-service/requirements.txt`:
```
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
python-multipart==0.0.6
httpx==0.26.0
faster-whisper==1.0.3
numpy>=1.24.0
pytest==8.2.0
```
(`yt-dlp` and `requests` removed.)

- [ ] **Step 2: Create transcription module**

`apps/audio-service/app/transcription.py`:
```python
import os
from typing import Optional

from faster_whisper import WhisperModel

WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")
_model: Optional[WhisperModel] = None


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def transcribe_file(path: str) -> dict:
    model = get_model()
    segments, info = model.transcribe(path, beam_size=5, language=None, vad_filter=True)
    text = " ".join(seg.text.strip() for seg in segments)
    return {
        "transcript": text,
        "language": info.language,
        "duration": float(getattr(info, "duration", 0.0)),
    }
```

- [ ] **Step 3: Rewrite main.py (transcription endpoint only; extractor added in Task 6)**

`apps/audio-service/app/main.py`:
```python
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .transcription import transcribe_file

app = FastAPI(title="Recipe ML Service", version="2.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))
TEMP_DIR = Path(tempfile.gettempdir()) / "recipe-uploads"
TEMP_DIR.mkdir(exist_ok=True)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "recipe-ml"}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    suffix = Path(file.filename or "upload").suffix or ".bin"
    tmp_path = TEMP_DIR / f"{os.urandom(8).hex()}{suffix}"
    try:
        tmp_path.write_bytes(data)
        result = transcribe_file(str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)
    return result
```

- [ ] **Step 4: Write the failing tests**

`apps/audio-service/tests/test_transcribe.py`:
```python
import io
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_transcribe_returns_text():
    fake = {"transcript": "mix the flour", "language": "en", "duration": 12.0}
    with patch("app.main.transcribe_file", return_value=fake):
        resp = client.post(
            "/transcribe",
            files={"file": ("a.wav", io.BytesIO(b"RIFFfakeaudio"), "audio/wav")},
        )
    assert resp.status_code == 200
    assert resp.json() == fake


def test_transcribe_rejects_empty():
    resp = client.post(
        "/transcribe", files={"file": ("a.wav", io.BytesIO(b""), "audio/wav")}
    )
    assert resp.status_code == 400
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd apps/audio-service && pip install -r requirements.txt && python -m pytest tests/test_transcribe.py -v`
Expected: 3 passed (real Whisper never loads because `transcribe_file` is patched; the empty-file test rejects before transcription).

- [ ] **Step 6: Commit**

```bash
git add apps/audio-service
git commit -m "feat(ml): transcribe uploaded files, drop yt-dlp"
```

---

### Task 6: FastAPI ML service — pluggable recipe extractor

**Files:**
- Create: `apps/audio-service/app/extractor.py`
- Create: `apps/audio-service/app/prompt.py`
- Modify: `apps/audio-service/app/main.py` (add `POST /extract`)
- Test: `apps/audio-service/tests/test_extractor.py`

**Interfaces:**
- Consumes: transcription endpoint from Task 5.
- Produces: `POST /extract` (JSON body `{"transcript": str, "title": str|None}`) returning the Recipe JSON shape; `parse_recipe_response(text) -> dict` (lenient parser); `get_extractor()` factory returning an object with `.extract(transcript, title) -> dict`, selected by env `EXTRACTOR_BACKEND` (`local` default, `hosted`).

- [ ] **Step 1: Port the prompt**

`apps/audio-service/app/prompt.py`:
```python
RECIPE_EXTRACTION_PROMPT = """You are a culinary expert that extracts structured recipe information from video transcripts.

Analyze the following transcript from a cooking video and extract the recipe details. Return ONLY valid JSON matching this exact structure:

{
  "title": "Recipe name",
  "description": "Brief 1-2 sentence description of the dish",
  "ingredients": [
    {"name": "ingredient name", "amount": "quantity as string", "unit": "measurement unit (optional)", "notes": "notes like 'diced' (optional)"}
  ],
  "instructions": [
    {"step": 1, "text": "Clear instruction text", "duration": "time if mentioned (optional)"}
  ],
  "tags": ["relevant", "tags"],
  "cuisine": "cuisine type if identifiable",
  "cook_time_minutes": null,
  "prep_time_minutes": null,
  "servings": null,
  "difficulty": "easy"
}

Guidelines:
- Extract ALL ingredients mentioned
- Number instructions sequentially
- Use null for unknown values
- Return ONLY the JSON, no other text

Transcript:
"""


def build_prompt(transcript: str, title: str | None) -> str:
    if title:
        return f"{RECIPE_EXTRACTION_PROMPT}\n\nVideo Title: {title}\n\n{transcript}"
    return f"{RECIPE_EXTRACTION_PROMPT}\n\n{transcript}"
```

- [ ] **Step 2: Create extractor with lenient parser and backends**

`apps/audio-service/app/extractor.py`:
```python
import json
import os
import re

import httpx

from .prompt import build_prompt


def parse_recipe_response(text: str) -> dict:
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
    if fence:
        s = fence.group(1)
    obj = re.search(r"\{[\s\S]*\}", s)
    if obj:
        s = obj.group(0)
    recipe = json.loads(s)
    if not recipe.get("title"):
        raise ValueError("Missing required field: title")
    recipe.setdefault("ingredients", [])
    recipe.setdefault("instructions", [])
    recipe.setdefault("tags", [])
    return recipe


class LocalGemmaExtractor:
    """Calls a local Ollama server running Gemma 3n."""

    def __init__(self):
        self.url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.model = os.environ.get("GEMMA_MODEL", "gemma3n")

    def extract(self, transcript: str, title: str | None) -> dict:
        prompt = build_prompt(transcript, title)
        resp = httpx.post(
            f"{self.url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=180,
        )
        resp.raise_for_status()
        return parse_recipe_response(resp.json()["response"])


class HostedExtractor:
    """Calls a hosted LLM API (OpenAI-compatible chat completions)."""

    def __init__(self):
        self.url = os.environ.get("HOSTED_LLM_URL", "")
        self.api_key = os.environ.get("HOSTED_LLM_API_KEY", "")
        self.model = os.environ.get("HOSTED_LLM_MODEL", "")

    def extract(self, transcript: str, title: str | None) -> dict:
        prompt = build_prompt(transcript, title)
        resp = httpx.post(
            self.url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=180,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return parse_recipe_response(content)


def get_extractor():
    backend = os.environ.get("EXTRACTOR_BACKEND", "local").lower()
    return HostedExtractor() if backend == "hosted" else LocalGemmaExtractor()
```

- [ ] **Step 3: Add `/extract` endpoint to main.py**

In `apps/audio-service/app/main.py` add near the top:
```python
from pydantic import BaseModel

from .extractor import get_extractor
```
and append:
```python
class ExtractRequest(BaseModel):
    transcript: str
    title: str | None = None


@app.post("/extract")
async def extract(req: ExtractRequest):
    extractor = get_extractor()
    try:
        return extractor.extract(req.transcript, req.title)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Extraction failed: {e}")
```

- [ ] **Step 4: Write the failing tests**

`apps/audio-service/tests/test_extractor.py`:
```python
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.extractor import parse_recipe_response
from app.main import app

client = TestClient(app)


def test_parse_strips_markdown_fence():
    raw = '```json\n{"title": "Soup", "ingredients": [], "instructions": []}\n```'
    assert parse_recipe_response(raw)["title"] == "Soup"


def test_parse_extracts_object_amid_prose():
    raw = 'Here you go: {"title": "Soup"} hope it helps'
    out = parse_recipe_response(raw)
    assert out["title"] == "Soup"
    assert out["ingredients"] == []  # defaulted


def test_parse_requires_title():
    with pytest.raises(ValueError):
        parse_recipe_response('{"description": "x"}')


def test_extract_endpoint_uses_extractor():
    fake = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}

    class Stub:
        def extract(self, transcript, title):
            return fake

    with patch("app.main.get_extractor", return_value=Stub()):
        resp = client.post("/extract", json={"transcript": "boil pasta", "title": "Pasta"})
    assert resp.status_code == 200
    assert resp.json() == fake
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd apps/audio-service && python -m pytest tests/ -v`
Expected: all passed (no real LLM loaded — extractor stubbed, parser pure).

- [ ] **Step 6: Commit**

```bash
git add apps/audio-service
git commit -m "feat(ml): pluggable recipe extractor (local gemma / hosted)"
```

---

### Task 7: Django ML client + Celery extraction task

**Files:**
- Create: `apps/web/config/celery.py`
- Modify: `apps/web/config/__init__.py` (load celery app)
- Create: `apps/web/recipes/ml_client.py`
- Create: `apps/web/recipes/tasks.py`
- Test: `apps/web/recipes/tests/test_tasks.py`

**Interfaces:**
- Consumes: `ExtractionJob`, `Recipe`, ML service endpoints `/transcribe` and `/extract`.
- Produces: `ml_client.transcribe(file_bytes, filename) -> dict`, `ml_client.extract(transcript, title) -> dict`; Celery task `run_extraction_job(job_id, file_path=None, transcript=None)` that drives the job statuses and creates a `Recipe`. `file_path` is a path to a temp upload saved by the view (Task 8); for paste-transcript, `transcript` is passed and Whisper is skipped.

- [ ] **Step 1: Create Celery app**

`apps/web/config/celery.py`:
```python
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
app = Celery("recipe")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

`apps/web/config/__init__.py`:
```python
from .celery import app as celery_app

__all__ = ("celery_app",)
```

- [ ] **Step 2: Create ML client**

`apps/web/recipes/ml_client.py`:
```python
import httpx
from django.conf import settings


def transcribe(file_bytes: bytes, filename: str) -> dict:
    resp = httpx.post(
        f"{settings.ML_SERVICE_URL}/transcribe",
        files={"file": (filename, file_bytes)},
        timeout=600,
    )
    resp.raise_for_status()
    return resp.json()


def extract(transcript: str, title: str | None) -> dict:
    resp = httpx.post(
        f"{settings.ML_SERVICE_URL}/extract",
        json={"transcript": transcript, "title": title},
        timeout=600,
    )
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 3: Create the Celery task**

`apps/web/recipes/tasks.py`:
```python
from pathlib import Path

from celery import shared_task

from . import ml_client
from .models import ExtractionJob, Recipe


def _set(job, status, label=""):
    job.status = status
    job.step_label = label
    job.save(update_fields=["status", "step_label", "updated_at"])


@shared_task
def run_extraction_job(job_id, file_path=None, transcript=None):
    job = ExtractionJob.objects.get(pk=job_id)
    try:
        if transcript is None:
            _set(job, ExtractionJob.Status.TRANSCRIBING, "Transcribing audio...")
            data = Path(file_path).read_bytes()
            result = ml_client.transcribe(data, Path(file_path).name)
            transcript = result["transcript"]

        _set(job, ExtractionJob.Status.EXTRACTING, "Extracting recipe...")
        summary = ml_client.extract(transcript, job.title or None)

        recipe = Recipe.objects.create(
            owner=job.owner,
            youtube_video_id=job.youtube_video_id,
            title=summary["title"],
            description=summary.get("description", ""),
            ingredients=summary.get("ingredients", []),
            instructions=summary.get("instructions", []),
            tags=summary.get("tags", []),
            cuisine=summary.get("cuisine", "") or "",
            cook_time_minutes=summary.get("cook_time_minutes"),
            prep_time_minutes=summary.get("prep_time_minutes"),
            servings=summary.get("servings"),
            difficulty=summary.get("difficulty", "") or "",
        )
        job.recipe = recipe
        _set(job, ExtractionJob.Status.DONE, "Done")
    except Exception as e:  # noqa: BLE001
        job.error = str(e)
        _set(job, ExtractionJob.Status.FAILED, "Failed")
    finally:
        if file_path:
            Path(file_path).unlink(missing_ok=True)
```

- [ ] **Step 4: Write the failing tests**

`apps/web/recipes/tests/test_tasks.py`:
```python
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from recipes.models import ExtractionJob, Recipe
from recipes.tasks import run_extraction_job

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@e.com", password="supersecret")


def test_paste_transcript_skips_whisper_and_creates_recipe(user):
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.PASTE_TRANSCRIPT, title="Pasta"
    )
    summary = {"title": "Pasta", "description": "yum", "ingredients": [{"name": "flour"}],
               "instructions": [{"step": 1, "text": "mix"}], "tags": ["italian"]}
    with patch("recipes.tasks.ml_client.extract", return_value=summary) as ex, \
         patch("recipes.tasks.ml_client.transcribe") as tr:
        run_extraction_job(job.id, transcript="boil pasta")
    tr.assert_not_called()
    ex.assert_called_once()
    job.refresh_from_db()
    assert job.status == ExtractionJob.Status.DONE
    assert job.recipe is not None
    assert Recipe.objects.get(pk=job.recipe_id).title == "Pasta"


def test_failure_marks_job_failed(user):
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.PASTE_TRANSCRIPT
    )
    with patch("recipes.tasks.ml_client.extract", side_effect=RuntimeError("boom")):
        run_extraction_job(job.id, transcript="x")
    job.refresh_from_db()
    assert job.status == ExtractionJob.Status.FAILED
    assert "boom" in job.error
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd apps/web && python -m pytest recipes/tests/test_tasks.py -v`
Expected: 2 passed. (Calling the task function directly runs it synchronously.)

- [ ] **Step 6: Commit**

```bash
git add apps/web
git commit -m "feat(web): ml client and celery extraction task"
```

---

### Task 8: Ingestion entry points (upload / paste) + job creation

**Files:**
- Modify: `apps/web/recipes/views.py` (add `start_job` view)
- Modify: `apps/web/recipes/urls.py` (add `start_job` route)
- Create (replace placeholder): `apps/web/templates/recipes/_ingest_panel.html`
- Create: `apps/web/templates/recipes/_job_status.html`
- Test: `apps/web/recipes/tests/test_ingest.py`

**Interfaces:**
- Consumes: `ExtractionJob`, `run_extraction_job` task.
- Produces: named URL `start_job` (POST). It accepts form fields: `source` (`upload|paste_transcript|paste_text`), optional `youtube_video_id`, optional `title`, optional file `media`, optional `transcript`/`text`. It creates an `ExtractionJob`, saves any upload to a temp path, enqueues `run_extraction_job`, and returns the `_job_status.html` partial (which polls `job_status`, defined in Task 9).

- [ ] **Step 1: Add the start_job view**

In `apps/web/recipes/views.py` add imports and view:
```python
import tempfile
from pathlib import Path

from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import ExtractionJob
from .tasks import run_extraction_job


@login_required
@require_POST
def start_job(request):
    source = request.POST.get("source", "upload")
    job = ExtractionJob.objects.create(
        owner=request.user,
        source=source,
        youtube_video_id=request.POST.get("youtube_video_id", ""),
        title=request.POST.get("title", ""),
    )

    if source == ExtractionJob.Source.PASTE_TRANSCRIPT:
        transcript = request.POST.get("transcript", "").strip()
        run_extraction_job.delay(job.id, transcript=transcript)
    elif source == ExtractionJob.Source.PASTE_TEXT:
        text = request.POST.get("text", "").strip()
        run_extraction_job.delay(job.id, transcript=text)
    else:  # upload
        upload = request.FILES["media"]
        tmp_dir = Path(tempfile.gettempdir()) / "recipe-web-uploads"
        tmp_dir.mkdir(exist_ok=True)
        tmp_path = tmp_dir / f"{job.id}_{upload.name}"
        with open(tmp_path, "wb") as f:
            for chunk in upload.chunks():
                f.write(chunk)
        run_extraction_job.delay(job.id, file_path=str(tmp_path))

    return render(request, "recipes/_job_status.html", {"job": job})
```

- [ ] **Step 2: Add route**

In `apps/web/recipes/urls.py` add:
```python
    path("jobs/start/", views.start_job, name="start_job"),
```

- [ ] **Step 3: Replace the ingest panel placeholder**

`apps/web/templates/recipes/_ingest_panel.html`:
```html
<div class="ingest" x-data="{ mode: 'upload' }">
  <div>
    <button type="button" @click="mode='upload'">Upload audio</button>
    <button type="button" @click="mode='transcript'">Paste transcript</button>
  </div>

  <form x-show="mode==='upload'" hx-post="{% url 'start_job' %}"
        hx-target="#job-{{ video.id }}" enctype="multipart/form-data">
    {% csrf_token %}
    <input type="hidden" name="source" value="upload">
    <input type="hidden" name="youtube_video_id" value="{{ video.id }}">
    <input type="hidden" name="title" value="{{ video.title }}">
    <input type="file" name="media" accept="audio/*,video/*" required>
    <button type="submit">Extract recipe</button>
  </form>

  <form x-show="mode==='transcript'" hx-post="{% url 'start_job' %}"
        hx-target="#job-{{ video.id }}">
    {% csrf_token %}
    <input type="hidden" name="source" value="paste_transcript">
    <input type="hidden" name="youtube_video_id" value="{{ video.id }}">
    <input type="hidden" name="title" value="{{ video.title }}">
    <textarea name="transcript" placeholder="Paste the transcript..." required></textarea>
    <button type="submit">Extract recipe</button>
  </form>

  <div id="job-{{ video.id }}"></div>
</div>
```

- [ ] **Step 4: Create the job status partial (initial render)**

`apps/web/templates/recipes/_job_status.html`:
```html
<div hx-get="{% url 'job_status' job.id %}" hx-trigger="load delay:1500ms"
     hx-swap="outerHTML">
  <p>Status: {{ job.step_label|default:job.get_status_display }}</p>
</div>
```

> Note: `job_status` URL is created in Task 9. Because templates resolve URLs at render time, Task 9 must be implemented for `start_job` to render. To keep THIS task testable independently, the test patches `run_extraction_job.delay` and asserts the job row + enqueue, and adds a minimal `job_status` URL stub. Implement Task 9 immediately after; do not ship the stub. If executing strictly in order, add the stub route now:
> in `recipes/urls.py` temporarily add `path("jobs/<int:pk>/status/", views.discover, name="job_status")` and replace it in Task 9.

- [ ] **Step 5: Write the failing tests**

`apps/web/recipes/tests/test_ingest.py`:
```python
import io
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from recipes.models import ExtractionJob

User = get_user_model()


@pytest.fixture
def auth_client(client, db):
    User.objects.create_user(email="u@e.com", password="supersecret")
    client.login(username="u@e.com", password="supersecret")
    return client


def test_paste_transcript_creates_job_and_enqueues(auth_client):
    with patch("recipes.views.run_extraction_job.delay") as delay:
        resp = auth_client.post("/jobs/start/", {
            "source": "paste_transcript", "youtube_video_id": "abc",
            "title": "Pasta", "transcript": "boil pasta"})
    assert resp.status_code == 200
    job = ExtractionJob.objects.get()
    assert job.source == "paste_transcript"
    delay.assert_called_once_with(job.id, transcript="boil pasta")


def test_upload_saves_file_and_enqueues(auth_client):
    with patch("recipes.views.run_extraction_job.delay") as delay:
        resp = auth_client.post("/jobs/start/", {
            "source": "upload", "youtube_video_id": "abc", "title": "Pasta",
            "media": io.BytesIO(b"fakeaudio")}, format="multipart")
    assert resp.status_code == 200
    job = ExtractionJob.objects.get()
    assert delay.call_args.args[0] == job.id
    assert "file_path" in delay.call_args.kwargs
```

> The Django test client sends a `BytesIO` as a file when the value has a `read` method; if needed wrap with `SimpleUploadedFile`. Use:
> `from django.core.files.uploadedfile import SimpleUploadedFile` and pass `"media": SimpleUploadedFile("a.wav", b"fakeaudio", content_type="audio/wav")`.

- [ ] **Step 6: Run tests to verify pass**

Run: `cd apps/web && python -m pytest recipes/tests/test_ingest.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add apps/web
git commit -m "feat(web): upload and paste ingestion entry points"
```

---

### Task 9: Job status polling endpoint

**Files:**
- Modify: `apps/web/recipes/views.py` (add `job_status`; remove the Task 8 stub route)
- Modify: `apps/web/recipes/urls.py` (real `job_status` route)
- Create: `apps/web/templates/recipes/_job_status_poll.html`
- Test: `apps/web/recipes/tests/test_job_status.py`

**Interfaces:**
- Consumes: `ExtractionJob`.
- Produces: named URL `job_status` (GET, `<int:pk>`). While running, returns a partial that re-polls itself; on `done`, returns a partial with an HTMX redirect (`HX-Redirect` header) to the recipe detail; on `failed`, shows the error. Owner-scoped (404 for other users).

- [ ] **Step 1: Add the view**

In `apps/web/recipes/views.py`:
```python
from django.http import HttpResponse
from django.shortcuts import get_object_or_404


@login_required
def job_status(request, pk):
    job = get_object_or_404(ExtractionJob, pk=pk, owner=request.user)
    if job.status == ExtractionJob.Status.DONE and job.recipe_id:
        resp = HttpResponse(status=204)
        resp["HX-Redirect"] = reverse("recipe_detail", args=[job.recipe_id])
        return resp
    return render(request, "recipes/_job_status_poll.html", {"job": job})
```

- [ ] **Step 2: Replace the route**

In `apps/web/recipes/urls.py` replace the Task 8 stub line with:
```python
    path("jobs/<int:pk>/status/", views.job_status, name="job_status"),
```

- [ ] **Step 3: Create the polling partial**

`apps/web/templates/recipes/_job_status_poll.html`:
```html
{% if job.status == 'failed' %}
<div><p>Extraction failed: {{ job.error }}</p></div>
{% else %}
<div hx-get="{% url 'job_status' job.id %}" hx-trigger="load delay:1500ms"
     hx-swap="outerHTML">
  <p>{{ job.step_label|default:job.get_status_display }}</p>
</div>
{% endif %}
```

- [ ] **Step 4: Write the failing tests**

`apps/web/recipes/tests/test_job_status.py`:
```python
import pytest
from django.contrib.auth import get_user_model

from recipes.models import ExtractionJob, Recipe

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@e.com", password="supersecret")


@pytest.fixture
def auth_client(client, user):
    client.login(username="u@e.com", password="supersecret")
    return client


def test_running_job_renders_poller(auth_client, user):
    job = ExtractionJob.objects.create(
        owner=user, source="upload", status=ExtractionJob.Status.EXTRACTING,
        step_label="Extracting recipe...")
    resp = auth_client.get(f"/jobs/{job.id}/status/")
    assert resp.status_code == 200
    assert b"Extracting recipe" in resp.content


def test_done_job_redirects(auth_client, user):
    recipe = Recipe.objects.create(owner=user, title="Pasta")
    job = ExtractionJob.objects.create(
        owner=user, source="upload", status=ExtractionJob.Status.DONE, recipe=recipe)
    resp = auth_client.get(f"/jobs/{job.id}/status/")
    assert resp.status_code == 204
    assert resp["HX-Redirect"] == f"/recipes/{recipe.id}/"


def test_other_users_job_404(auth_client, db):
    other = User.objects.create_user(email="o@e.com", password="supersecret")
    job = ExtractionJob.objects.create(owner=other, source="upload")
    resp = auth_client.get(f"/jobs/{job.id}/status/")
    assert resp.status_code == 404
```

> Note: `recipe_detail` URL (path `recipes/<int:pk>/`) is created in Task 10. Add it now as part of this task's prerequisites OR implement Task 10 before running the `test_done_job_redirects` assertion on the exact path. To keep ordering clean, this task assumes Task 10's `recipe_detail` route name exists; if running strictly in order, temporarily add `path("recipes/<int:pk>/", views.discover, name="recipe_detail")` and replace in Task 10.

- [ ] **Step 5: Run tests to verify pass**

Run: `cd apps/web && python -m pytest recipes/tests/test_job_status.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/web
git commit -m "feat(web): job status polling with htmx redirect on completion"
```

---

### Task 10: Saved, Favorites, Recipe detail, Profile pages

**Files:**
- Modify: `apps/web/recipes/views.py` (add `saved`, `favorites`, `recipe_detail`, `toggle_favorite`, `delete_recipe`)
- Modify: `apps/web/recipes/urls.py` (routes; replace any Task 9 stub for `recipe_detail`)
- Create: `apps/web/accounts/views.py` profile view (append) + route
- Create: `apps/web/templates/recipes/saved.html`
- Create: `apps/web/templates/recipes/favorites.html`
- Create: `apps/web/templates/recipes/detail.html`
- Create: `apps/web/templates/recipes/_recipe_card.html`
- Create: `apps/web/templates/accounts/profile.html`
- Test: `apps/web/recipes/tests/test_pages.py`

**Interfaces:**
- Consumes: `Recipe`, `Favorite`.
- Produces: named URLs `saved`, `favorites`, `recipe_detail` (`recipes/<int:pk>/`), `toggle_favorite` (POST `recipes/<int:pk>/favorite/`), `delete_recipe` (POST `recipes/<int:pk>/delete/`), `profile`. All owner-scoped.

- [ ] **Step 1: Add recipe list/detail/favorite/delete views**

In `apps/web/recipes/views.py`:
```python
from django.db.models import Exists, OuterRef

from .models import Favorite, Recipe


def _annotated(qs, user):
    fav = Favorite.objects.filter(user=user, recipe=OuterRef("pk"))
    return qs.annotate(is_favorite=Exists(fav))


@login_required
def saved(request):
    q = request.GET.get("q", "").strip()
    recipes = _annotated(Recipe.objects.filter(owner=request.user), request.user)
    if q:
        recipes = recipes.filter(title__icontains=q)
    return render(request, "recipes/saved.html", {"recipes": recipes, "q": q})


@login_required
def favorites(request):
    recipes = _annotated(
        Recipe.objects.filter(owner=request.user, favorited_by__user=request.user),
        request.user,
    )
    return render(request, "recipes/favorites.html", {"recipes": recipes})


@login_required
def recipe_detail(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, owner=request.user)
    is_fav = Favorite.objects.filter(user=request.user, recipe=recipe).exists()
    return render(request, "recipes/detail.html", {"recipe": recipe, "is_favorite": is_fav})


@login_required
@require_POST
def toggle_favorite(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, owner=request.user)
    fav, created = Favorite.objects.get_or_create(user=request.user, recipe=recipe)
    if not created:
        fav.delete()
    recipe.is_favorite = created
    return render(request, "recipes/_recipe_card.html", {"recipe": recipe})


@login_required
@require_POST
def delete_recipe(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, owner=request.user)
    recipe.delete()
    resp = HttpResponse(status=204)
    resp["HX-Redirect"] = reverse("saved")
    return resp
```

- [ ] **Step 2: Add routes**

In `apps/web/recipes/urls.py` (replace the Task 9 `recipe_detail` stub if present):
```python
    path("saved/", views.saved, name="saved"),
    path("favorites/", views.favorites, name="favorites"),
    path("recipes/<int:pk>/", views.recipe_detail, name="recipe_detail"),
    path("recipes/<int:pk>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("recipes/<int:pk>/delete/", views.delete_recipe, name="delete_recipe"),
```

- [ ] **Step 3: Add profile view + route**

Append to `apps/web/accounts/views.py`:
```python
from django.contrib.auth.decorators import login_required


@login_required
def profile(request):
    if request.method == "POST":
        request.user.display_name = request.POST.get("display_name", "")
        request.user.save(update_fields=["display_name"])
    return render(request, "accounts/profile.html")
```
Add to `apps/web/accounts/urls.py`:
```python
    path("profile/", profile, name="profile"),
```
and import `profile` in that file's import line.

- [ ] **Step 4: Create templates**

`apps/web/templates/recipes/_recipe_card.html`:
```html
<div class="recipe-card" id="recipe-{{ recipe.id }}">
  <a href="{% url 'recipe_detail' recipe.id %}">{{ recipe.title }}</a>
  <form hx-post="{% url 'toggle_favorite' recipe.id %}" hx-target="#recipe-{{ recipe.id }}"
        hx-swap="outerHTML">
    {% csrf_token %}
    <button type="submit">{% if recipe.is_favorite %}♥{% else %}♡{% endif %}</button>
  </form>
</div>
```

`apps/web/templates/recipes/saved.html`:
```html
{% extends "base.html" %}
{% block title %}Saved{% endblock %}
{% block content %}
<h1>Saved recipes</h1>
<input type="search" name="q" value="{{ q }}" placeholder="Search saved..."
       hx-get="{% url 'saved' %}" hx-target="#recipe-list" hx-select="#recipe-list"
       hx-trigger="keyup changed delay:400ms">
<div id="recipe-list">
  {% for recipe in recipes %}{% include "recipes/_recipe_card.html" %}
  {% empty %}<p>No recipes yet. Extract one from the Discover tab.</p>{% endfor %}
</div>
{% endblock %}
```

`apps/web/templates/recipes/favorites.html`:
```html
{% extends "base.html" %}
{% block title %}Favorites{% endblock %}
{% block content %}
<h1>Favorites</h1>
<div id="recipe-list">
  {% for recipe in recipes %}{% include "recipes/_recipe_card.html" %}
  {% empty %}<p>No favorites yet.</p>{% endfor %}
</div>
{% endblock %}
```

`apps/web/templates/recipes/detail.html`:
```html
{% extends "base.html" %}
{% block title %}{{ recipe.title }}{% endblock %}
{% block content %}
<h1>{{ recipe.title }}</h1>
<p>{{ recipe.description }}</p>
{% if recipe.youtube_video_id %}
<iframe width="320" height="180" src="https://www.youtube.com/embed/{{ recipe.youtube_video_id }}"
        frameborder="0" allowfullscreen></iframe>
{% endif %}
<h2>Ingredients</h2>
<ul>{% for i in recipe.ingredients %}<li>{{ i.amount }} {{ i.unit }} {{ i.name }}{% if i.notes %} ({{ i.notes }}){% endif %}</li>{% endfor %}</ul>
<h2>Instructions</h2>
<ol>{% for s in recipe.instructions %}<li>{{ s.text }}{% if s.duration %} — {{ s.duration }}{% endif %}</li>{% endfor %}</ol>
<form hx-post="{% url 'toggle_favorite' recipe.id %}" hx-target="this" hx-swap="outerHTML">
  {% csrf_token %}<button type="submit">{% if is_favorite %}Unfavorite{% else %}Favorite{% endif %}</button>
</form>
<form hx-post="{% url 'delete_recipe' recipe.id %}">{% csrf_token %}<button type="submit">Delete</button></form>
{% endblock %}
```

`apps/web/templates/accounts/profile.html`:
```html
{% extends "base.html" %}
{% block title %}Profile{% endblock %}
{% block content %}
<h1>Profile</h1>
<p>Email: {{ user.email }}</p>
<form method="post">{% csrf_token %}
  <label>Display name <input name="display_name" value="{{ user.display_name }}"></label>
  <button type="submit">Save</button>
</form>
{% endblock %}
```

- [ ] **Step 5: Write the failing tests**

`apps/web/recipes/tests/test_pages.py`:
```python
import pytest
from django.contrib.auth import get_user_model

from recipes.models import Favorite, Recipe

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@e.com", password="supersecret")


@pytest.fixture
def auth_client(client, user):
    client.login(username="u@e.com", password="supersecret")
    return client


def test_saved_lists_only_owner_recipes(auth_client, user):
    other = User.objects.create_user(email="o@e.com", password="supersecret")
    Recipe.objects.create(owner=user, title="Mine")
    Recipe.objects.create(owner=other, title="Theirs")
    resp = auth_client.get("/saved/")
    assert b"Mine" in resp.content
    assert b"Theirs" not in resp.content


def test_saved_search_filters(auth_client, user):
    Recipe.objects.create(owner=user, title="Tomato Soup")
    Recipe.objects.create(owner=user, title="Pancakes")
    resp = auth_client.get("/saved/", {"q": "soup"})
    assert b"Tomato Soup" in resp.content
    assert b"Pancakes" not in resp.content


def test_toggle_favorite_adds_then_removes(auth_client, user):
    r = Recipe.objects.create(owner=user, title="Pasta")
    auth_client.post(f"/recipes/{r.id}/favorite/")
    assert Favorite.objects.filter(user=user, recipe=r).exists()
    auth_client.post(f"/recipes/{r.id}/favorite/")
    assert not Favorite.objects.filter(user=user, recipe=r).exists()


def test_favorites_lists_only_favorited(auth_client, user):
    r1 = Recipe.objects.create(owner=user, title="Fav")
    Recipe.objects.create(owner=user, title="NotFav")
    Favorite.objects.create(user=user, recipe=r1)
    resp = auth_client.get("/favorites/")
    assert b"Fav" in resp.content
    assert b"NotFav" not in resp.content


def test_delete_recipe(auth_client, user):
    r = Recipe.objects.create(owner=user, title="Gone")
    resp = auth_client.post(f"/recipes/{r.id}/delete/")
    assert resp.status_code == 204
    assert not Recipe.objects.filter(pk=r.id).exists()


def test_profile_updates_display_name(auth_client, user):
    auth_client.post("/profile/", {"display_name": "Chef Alex"})
    user.refresh_from_db()
    assert user.display_name == "Chef Alex"
```

- [ ] **Step 6: Run full web test suite**

Run: `cd apps/web && python -m pytest -v`
Expected: all tests across all tasks pass.

- [ ] **Step 7: Commit**

```bash
git add apps/web
git commit -m "feat(web): saved, favorites, recipe detail, and profile pages"
```

---

### Task 11: Docker Compose, Dockerfiles, env, and cleanup

**Files:**
- Create: `apps/web/Dockerfile`
- Modify: `apps/audio-service/Dockerfile` (keep ffmpeg, models download on first use; no yt-dlp-specific bits needed)
- Rewrite: `docker-compose.yml`
- Rewrite: `.env.example`
- Modify: root `package.json` (remove mobile/api workspaces scripts that no longer apply; keep docker scripts)
- Delete: `apps/mobile/`, `apps/api/`, `docker/kong/`, `docker/db/`, `packages/shared/`, `apps/audio-service/app/main.py`'s old yt-dlp endpoints (already gone in Task 5)
- Test: manual end-to-end smoke (documented commands)

**Interfaces:**
- Consumes: all prior tasks.
- Produces: `docker compose up` brings up `db` (postgres), `redis`, `web` (Django+gunicorn), `worker` (celery), `ml` (FastAPI). Web reachable at `http://localhost:8000`.

- [ ] **Step 1: Create the web Dockerfile**

`apps/web/Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV DJANGO_SETTINGS_MODULE=config.settings
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:8000"]
```

- [ ] **Step 2: Rewrite docker-compose.yml**

`docker-compose.yml`:
```yaml
services:
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_USER: recipe
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-recipe}
      POSTGRES_DB: recipe
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U recipe"]
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - "${POSTGRES_PORT:-5432}:5432"

  redis:
    image: redis:7
    restart: unless-stopped

  ml:
    build: ./apps/audio-service
    restart: unless-stopped
    environment:
      WHISPER_MODEL_SIZE: ${WHISPER_MODEL_SIZE:-base}
      EXTRACTOR_BACKEND: ${EXTRACTOR_BACKEND:-local}
      OLLAMA_URL: ${OLLAMA_URL:-http://host.docker.internal:11434}
      GEMMA_MODEL: ${GEMMA_MODEL:-gemma3n}
      HOSTED_LLM_URL: ${HOSTED_LLM_URL:-}
      HOSTED_LLM_API_KEY: ${HOSTED_LLM_API_KEY:-}
      HOSTED_LLM_MODEL: ${HOSTED_LLM_MODEL:-}
    ports:
      - "${ML_PORT:-8001}:8001"

  web:
    build: ./apps/web
    restart: unless-stopped
    environment:
      DATABASE_URL: postgres://recipe:${POSTGRES_PASSWORD:-recipe}@db:5432/recipe
      REDIS_URL: redis://redis:6379/0
      ML_SERVICE_URL: http://ml:8001
      YOUTUBE_API_KEY: ${YOUTUBE_API_KEY}
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:-dev-insecure-key-change-me}
      DJANGO_DEBUG: ${DJANGO_DEBUG:-false}
      DJANGO_ALLOWED_HOSTS: ${DJANGO_ALLOWED_HOSTS:-*}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    ports:
      - "${WEB_PORT:-8000}:8000"

  worker:
    build: ./apps/web
    restart: unless-stopped
    command: celery -A config worker -l info
    environment:
      DATABASE_URL: postgres://recipe:${POSTGRES_PASSWORD:-recipe}@db:5432/recipe
      REDIS_URL: redis://redis:6379/0
      ML_SERVICE_URL: http://ml:8001
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started

volumes:
  db-data:
```

- [ ] **Step 3: Rewrite .env.example**

`.env.example`:
```
# Postgres
POSTGRES_PASSWORD=recipe
POSTGRES_PORT=5432

# Django
DJANGO_SECRET_KEY=change-me-to-a-long-random-string
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=*
WEB_PORT=8000

# YouTube Data API
YOUTUBE_API_KEY=your-youtube-api-key

# ML service
ML_PORT=8001
WHISPER_MODEL_SIZE=base

# Recipe extractor: "local" (Ollama/Gemma) or "hosted"
EXTRACTOR_BACKEND=local
OLLAMA_URL=http://host.docker.internal:11434
GEMMA_MODEL=gemma3n

# Hosted fallback (used when EXTRACTOR_BACKEND=hosted)
HOSTED_LLM_URL=
HOSTED_LLM_API_KEY=
HOSTED_LLM_MODEL=

# Max uploaded media duration (seconds)
MAX_DURATION_SECONDS=900
```

- [ ] **Step 4: Remove obsolete code**

```bash
git rm -r apps/mobile apps/api packages/shared docker/kong docker/db
```
(If `packages/shared` is referenced anywhere else, leave it; otherwise remove. Verify with `grep -rn "packages/shared" --include=*.json .` first.)

- [ ] **Step 5: Update root package.json scripts**

Replace the `scripts` block in root `package.json` with docker-only scripts (mobile/api workspaces are gone):
```json
  "scripts": {
    "docker:start": "docker compose up --build",
    "docker:stop": "docker compose down",
    "docker:logs": "docker compose logs -f",
    "docker:reset": "docker compose down -v && docker compose up -d --build"
  },
```
Remove the `"workspaces"` array if `apps/mobile`/`apps/api`/`packages/*` were its only members, or set it to `[]`.

- [ ] **Step 6: Manual smoke test**

```bash
cp .env.example .env   # set YOUTUBE_API_KEY
docker compose up --build -d
curl -s localhost:8000/health/      # {"status": "ok"}
curl -s localhost:8001/health        # {"status":"healthy",...}
# create a superuser to log in:
docker compose exec web python manage.py createsuperuser
```
Then in a browser: log in, search a recipe, open a video, paste a transcript, watch the status poller drive to the saved recipe, favorite it, see it under Saved/Favorites.

Expected: full loop works; extraction requires either a running Ollama with the Gemma model (local) or hosted env vars set.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: docker compose, env, and remove mobile/api/supabase stack"
```

---

## Self-Review Notes

- **Spec coverage:** architecture split (T1,T5,T6,T11), data model (T3), email/password auth (T2), YouTube search + embed (T4), upload/paste ingestion (T8), Whisper on uploads (T5), pluggable extractor local+hosted (T6), Celery job + polling UX (T7,T9), all pages (T4,T10), error handling (T6 parser, T7 failed-job, T9 failed UI, T5 upload validation), testing throughout, repo cleanup (T11). Deferred per spec: OAuth/email-verify (not implemented, intentional).
- **Cross-task URL ordering:** `_results.html` (T4) references `_ingest_panel.html` (placeholder until T8); `start_job` (T8) renders `_job_status.html` referencing `job_status` (T9); `job_status` (T9) references `recipe_detail` (T10). Each forward reference is called out in the task with a temporary stub instruction so tasks stay independently runnable; stubs are replaced in the owning task. When executing with subagents, prefer implementing T8→T9→T10 in close sequence.
- **Type consistency:** `run_extraction_job(job_id, file_path=None, transcript=None)` signature consistent across T7 (def), T8 (`.delay` calls). ML endpoints `/transcribe`, `/extract` consistent across T5/T6 (server) and T7 (client). Recipe summary keys consistent between extractor output (T6) and `Recipe.objects.create` (T7).
