# Mise component library + onboarding wizard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the Mise design system into the Django web app as a reusable CSS component library and add a taste-preferences onboarding wizard that runs after signup.

**Architecture:** A static CSS layer (`tokens.css` + `components.css`) holds design tokens and component classes; `base.html` becomes the Mise app shell. Onboarding adds four preference fields to `accounts.User` and a stateless 3-step wizard that persists each step to the user row, gated so users with `onboarding_completed=False` are redirected into it.

**Tech Stack:** Django (server-rendered templates), WhiteNoise static files, htmx + Alpine (already loaded), pytest + pytest-django. CSS uses custom properties and the `:has()` selector for chip selection — **no new JS**.

## Global Constraints

- All work lives under `apps/web/`. Commands run from `apps/web/`.
- Django settings module: `config.settings`. Tests run via `pytest` (config in `apps/web/pytest.ini`).
- Custom user model: `accounts.User` (email is `USERNAME_FIELD`, no username field).
- Default palette is **Ember / light**; token values copied verbatim from `design/Mise Design System.dc.html` `:root`.
- Fonts: **Newsreader** (display/serif), **Hanken Grotesk** (UI body), **Spline Sans Mono** (meta/labels).
- `JSONField` list defaults MUST use the callable `default=list` (never `default=[]`).
- Preserve existing template contract: `_recipe_card.html` must keep `id="recipe-{{ recipe.id }}"`, the `href` to `recipe_detail`, the recipe title text, and the htmx favorite form. Existing tests in `recipes/tests/test_pages.py` and `accounts/tests/test_auth.py` must stay green.
- Run the full suite with `pytest -q` from `apps/web/` after each task.

---

## File Structure

**Create**
- `apps/web/static/css/tokens.css` — design tokens (CSS custom properties), font imports, base/reset, app-shell layout.
- `apps/web/static/css/components.css` — component classes (buttons, chips, badges, inputs, video card, recipe primitives, extraction state, onboarding wizard).
- `apps/web/accounts/constants.py` — cuisine / diet / cook-time option lists.
- `apps/web/accounts/migrations/0002_user_preferences.py` — preference fields migration.
- `apps/web/templates/accounts/onboarding_welcome.html`
- `apps/web/templates/accounts/onboarding_tastes.html`
- `apps/web/templates/accounts/onboarding_cook_time.html`
- `apps/web/templates/accounts/_onboarding_progress.html` — shared progress indicator partial.
- `apps/web/accounts/tests/test_onboarding.py`

**Modify**
- `apps/web/config/settings.py` — `STATICFILES_DIRS`, test-aware staticfiles storage.
- `apps/web/conftest.py` — set `DJANGO_TESTING` env so settings picks non-manifest storage.
- `apps/web/templates/base.html` — Mise shell, fonts, stylesheet links.
- `apps/web/templates/recipes/_recipe_card.html` — Mise video card.
- `apps/web/accounts/models.py` — four preference fields.
- `apps/web/accounts/views.py` — signup redirect, onboarding views, skip, gating decorator.
- `apps/web/accounts/urls.py` — onboarding routes.
- `apps/web/recipes/views.py` — apply `onboarding_required` to `discover`, `saved`, `favorites`.

---

## Task 1: Static foundation — tokens, fonts, app shell, test storage

**Files:**
- Create: `apps/web/static/css/tokens.css`
- Modify: `apps/web/config/settings.py`, `apps/web/conftest.py`, `apps/web/templates/base.html`
- Test: `apps/web/recipes/tests/test_pages.py` (existing — must stay green)

**Interfaces:**
- Produces: a `base.html` shell exposing CSS via `{% static 'css/tokens.css' %}` and `{% static 'css/components.css' %}` (the second file is created in Task 2; linking it now is harmless because the non-manifest test storage and dev WhiteNoise both tolerate a not-yet-existing file at template-render time — the link only resolves a URL string, it does not read the file).
- Produces: `_TESTING` settings branch keyed on `DJANGO_TESTING=1`.

- [ ] **Step 1: Make test runs use non-manifest static storage**

In `apps/web/conftest.py`, add the env flag at import time (before Django configures), keeping the existing line:

```python
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_TESTING", "1")
```

- [ ] **Step 2: Wire settings for project static dir + test storage**

In `apps/web/config/settings.py`, replace the existing `STORAGES = { ... }` block and the `STATIC_ROOT` line region with:

```python
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
```

- [ ] **Step 3: Create the tokens stylesheet**

Create `apps/web/static/css/tokens.css`:

```css
/* Mise design tokens — Ember / light (default). Values from the Mise design system. */
@import url("https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300..600;1,6..72,300..500&family=Hanken+Grotesk:wght@400;500;600;700;800&family=Spline+Sans+Mono:wght@400;500;600&display=swap");

:root {
  /* neutrals — warm clay */
  --paper: #F3E9D8;   --surface: #FCF7EC;   --surface-2: #EADDC6;
  --ink: #231C12;     --ink-2: #5A4F3D;     --muted: #948A74;
  --line: #E4D6BD;    --line-2: #D4C19F;
  --shadow-1: 0 1px 2px rgba(60,44,20,.05), 0 4px 14px rgba(60,44,20,.06);
  --shadow-2: 0 2px 6px rgba(60,44,20,.08), 0 16px 44px rgba(60,44,20,.13);

  /* accents — ember */
  --accent: #E0613B;        --accent-press: #C44E2A;
  --secondary: #E7A22F;     --secondary-press: #CC8A1E;
  --on-accent: #FFF6EF;

  /* derived */
  --accent-soft: color-mix(in srgb, var(--accent) 13%, var(--paper));
  --accent-softer: color-mix(in srgb, var(--accent) 7%, var(--paper));
  --accent-line: color-mix(in srgb, var(--accent) 30%, var(--line));
  --on-soft: var(--accent-press);
  --secondary-soft: color-mix(in srgb, var(--secondary) 16%, var(--paper));

  /* radius + spacing (base 4) */
  --r-sm: 8px;  --r-md: 12px;  --r-lg: 16px;  --r-xl: 18px;  --r-pill: 999px;
  --s-1: 4px; --s-2: 8px; --s-3: 12px; --s-4: 16px; --s-5: 20px; --s-6: 24px; --s-8: 32px;

  /* fonts */
  --font-ui: 'Hanken Grotesk', system-ui, sans-serif;
  --font-display: 'Newsreader', Georgia, serif;
  --font-mono: 'Spline Sans Mono', ui-monospace, monospace;
}

@keyframes mise-shimmer { 0% { background-position: -460px 0; } 100% { background-position: 460px 0; } }
@keyframes mise-spin { to { transform: rotate(360deg); } }
@keyframes mise-pulse { 0%,100% { opacity:.55; } 50% { opacity:1; } }

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--font-ui);
  -webkit-font-smoothing: antialiased;
}
::selection { background: color-mix(in srgb, var(--accent) 26%, transparent); }
a { color: var(--accent); text-decoration: none; }

/* app shell */
.app-bar {
  display: flex; align-items: center; justify-content: space-between; gap: 20px;
  padding: 16px 26px; border-bottom: 1px solid var(--line); background: var(--paper);
}
.app-bar__brand {
  font-family: var(--font-display); font-weight: 560; font-size: 23px;
  letter-spacing: -.01em; color: var(--ink);
}
.app-bar__nav { display: flex; align-items: center; gap: 20px; }
.app-bar__nav a, .app-bar__nav button {
  font-family: var(--font-ui); font-size: 14px; font-weight: 500; color: var(--ink-2);
  background: none; border: none; cursor: pointer; padding: 0;
}
.app-bar__nav a:hover { color: var(--accent); }
.app-main { max-width: 1080px; margin: 0 auto; padding: 26px; }
.flash { list-style: none; margin: 0; padding: 12px 26px; }
.flash li {
  padding: 10px 14px; border-radius: var(--r-md); background: var(--accent-soft);
  color: var(--on-soft); font-size: 14px; margin-bottom: 8px;
}
```

- [ ] **Step 4: Rebuild base.html as the Mise shell**

Replace the entire contents of `apps/web/templates/base.html`:

```html
{% load static %}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Mise{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/tokens.css' %}">
  <link rel="stylesheet" href="{% static 'css/components.css' %}">
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>
</head>
<body>
  <nav class="app-bar">
    <a class="app-bar__brand" href="{% url 'discover' %}">Mise</a>
    <div class="app-bar__nav">
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
    </div>
  </nav>
  {% if messages %}<ul class="flash">{% for m in messages %}<li>{{ m }}</li>{% endfor %}</ul>{% endif %}
  <main class="app-main">{% block content %}{% endblock %}</main>
</body>
</html>
```

- [ ] **Step 5: Run the existing suite to verify nothing broke**

Run: `cd apps/web && pytest -q`
Expected: PASS — same number of tests as before this task (the static link + shell must not break `test_pages.py` or `test_auth.py`).

- [ ] **Step 6: Commit**

```bash
git add apps/web/static/css/tokens.css apps/web/config/settings.py apps/web/conftest.py apps/web/templates/base.html
git commit -m "feat(web): Mise design tokens, fonts, and app shell"
```

---

## Task 2: Component library CSS + Mise video card

**Files:**
- Create: `apps/web/static/css/components.css`
- Modify: `apps/web/templates/recipes/_recipe_card.html`
- Test: `apps/web/recipes/tests/test_pages.py` (existing — must stay green)

**Interfaces:**
- Produces CSS classes consumed by later tasks and the card: `.btn` (+ `--primary`/`--secondary`/`--ghost`/`--icon`), `.chip` (+ `--selected`), `.badge` (+ `--ai`/`--source`/`--difficulty`/`--time`), `.search-field`, `.text-input`, `.select-field`, `.toggle`, `.video-card`, `.ingredient-row`, `.step`, `.extraction-state`.

- [ ] **Step 1: Create the components stylesheet**

Create `apps/web/static/css/components.css`:

```css
/* Mise components — consume tokens.css custom properties. */

/* buttons */
.btn {
  display: inline-flex; align-items: center; gap: 9px;
  padding: 12px 22px; border: none; border-radius: var(--r-pill);
  font-family: var(--font-ui); font-size: 15px; font-weight: 600;
  cursor: pointer; box-shadow: var(--shadow-1);
}
.btn--primary { background: var(--accent); color: var(--on-accent); }
.btn--primary:hover { background: var(--accent-press); }
.btn--secondary { background: var(--surface); color: var(--ink); border: 1px solid var(--line-2); box-shadow: none; }
.btn--secondary:hover { background: var(--surface-2); }
.btn--ghost { background: transparent; color: var(--accent); box-shadow: none; padding: 12px 16px; }
.btn--ghost:hover { background: var(--accent-soft); }
.btn:disabled { background: var(--surface-2); color: var(--muted); cursor: not-allowed; box-shadow: none; }
.btn--icon {
  width: 44px; height: 44px; padding: 0; justify-content: center; border-radius: 50%;
  background: var(--surface); color: var(--ink); border: 1px solid var(--line-2); box-shadow: none;
}
.btn--icon:hover { background: var(--surface-2); }

/* chips — selectable via a wrapped checkbox/radio using :has() */
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 15px; border-radius: var(--r-pill);
  background: var(--surface-2); border: 1px solid var(--line);
  color: var(--ink); font-size: 13.5px; font-weight: 500; cursor: pointer; user-select: none;
}
.chip input { position: absolute; opacity: 0; width: 0; height: 0; }
.chip--selected,
.chip:has(input:checked) { background: var(--accent); border-color: var(--accent); color: var(--on-accent); font-weight: 600; }

/* badges */
.badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: var(--r-pill);
  background: var(--surface-2); border: 1px solid var(--line);
  color: var(--ink); font-family: var(--font-mono); font-size: 12px; font-weight: 500;
}
.badge--ai { background: var(--accent-soft); border-color: transparent; color: var(--on-soft); }
.badge--source { font-family: var(--font-ui); font-size: 12.5px; font-weight: 600; color: var(--ink-2); }
.badge--difficulty { color: var(--ink); }
.badge--time { color: var(--ink); }

/* inputs */
.search-field {
  display: flex; align-items: center; gap: 11px;
  padding: 14px 18px; border: 1px solid var(--line-2); border-radius: var(--r-pill); background: var(--surface);
}
.search-field input {
  flex: 1; border: none; background: transparent; outline: none;
  font-family: var(--font-ui); font-size: 15.5px; color: var(--ink);
}
.text-input {
  width: 100%; padding: 13px 16px; border: 1px solid var(--line); border-radius: var(--r-md);
  background: var(--paper); font-family: var(--font-ui); font-size: 15px; color: var(--ink); outline: none;
}
.text-input:focus { border-color: var(--accent-line); }
.select-field {
  display: flex; align-items: center; justify-content: space-between;
  padding: 13px 16px; border: 1px solid var(--line); border-radius: var(--r-md); background: var(--paper);
}
.toggle { position: relative; width: 42px; height: 24px; border-radius: var(--r-pill); background: var(--surface-2); border: none; cursor: pointer; }
.toggle[aria-checked="true"] { background: var(--accent); }
.toggle::after {
  content: ""; position: absolute; top: 2px; left: 2px; width: 20px; height: 20px;
  border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.3); transition: left .15s;
}
.toggle[aria-checked="true"]::after { left: 20px; }

/* signature: video card */
.video-card {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg);
  overflow: hidden; box-shadow: var(--shadow-1);
}
.video-card__media {
  position: relative; aspect-ratio: 16/10;
  background: repeating-linear-gradient(45deg, var(--surface-2), var(--surface-2) 12px,
    color-mix(in srgb, var(--secondary) 17%, var(--surface-2)) 12px,
    color-mix(in srgb, var(--secondary) 17%, var(--surface-2)) 24px);
}
.video-card__media img { width: 100%; height: 100%; object-fit: cover; display: block; }
.video-card__body { padding: 15px 16px 17px; }
.video-card__title { font-family: var(--font-display); font-weight: 500; font-size: 21px; line-height: 1.15; margin: 0 0 7px; color: var(--ink); }
.video-card__title a { color: inherit; }
.video-card__meta { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; font-size: 13px; color: var(--ink-2); }
.video-card__foot { display: flex; align-items: center; justify-content: space-between; }
.video-card__tags { display: flex; gap: 6px; }

/* recipe primitives */
.ingredient-row { display: flex; align-items: center; gap: 13px; padding: 9px 0; border-bottom: 1px solid var(--line); }
.ingredient-row__amount { font-family: var(--font-mono); font-size: 13.5px; color: var(--accent); font-weight: 600; width: 70px; }
.ingredient-row--checked .ingredient-row__name { text-decoration: line-through; opacity: .55; }
.step { display: flex; gap: 16px; }
.step__num {
  flex: 0 0 auto; width: 30px; height: 30px; border-radius: 50%;
  background: var(--accent-soft); color: var(--on-soft); display: flex; align-items: center; justify-content: center;
  font-family: var(--font-display); font-size: 16px; font-weight: 600;
}
.step__jump {
  display: inline-flex; align-items: center; gap: 7px; padding: 6px 12px;
  border: 1px solid var(--accent-line); border-radius: var(--r-pill); background: transparent;
  color: var(--accent); font-family: var(--font-mono); font-size: 11.5px; font-weight: 500; cursor: pointer;
}
.step__jump:hover { background: var(--accent-soft); }

/* extraction state */
.extraction-state {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg);
  padding: 22px 24px; box-shadow: var(--shadow-1); display: flex; align-items: center; gap: 18px;
}
.extraction-state__bar { height: 8px; border-radius: var(--r-pill); background: var(--surface-2); overflow: hidden; }
.extraction-state__fill {
  height: 100%; border-radius: var(--r-pill);
  background: linear-gradient(90deg, var(--secondary), var(--accent)); background-size: 460px 100%;
  animation: mise-shimmer 1.4s linear infinite;
}
```

- [ ] **Step 2: Restyle the recipe card to the Mise video card (preserve contract)**

Replace `apps/web/templates/recipes/_recipe_card.html`:

```html
<div class="video-card" id="recipe-{{ recipe.id }}">
  <div class="video-card__media">
    {% if recipe.thumbnail_url %}<img src="{{ recipe.thumbnail_url }}" alt="">{% endif %}
  </div>
  <div class="video-card__body">
    <h4 class="video-card__title"><a href="{% url 'recipe_detail' recipe.id %}">{{ recipe.title }}</a></h4>
    {% if recipe.channel_name %}<div class="video-card__meta">{{ recipe.channel_name }}</div>{% endif %}
    <div class="video-card__foot">
      <div class="video-card__tags">
        {% if recipe.cook_time_minutes %}<span class="badge badge--time">{{ recipe.cook_time_minutes }} MIN</span>{% endif %}
        {% if recipe.difficulty %}<span class="badge badge--difficulty">{{ recipe.difficulty|upper }}</span>{% endif %}
      </div>
      <form hx-post="{% url 'toggle_favorite' recipe.id %}" hx-target="#recipe-{{ recipe.id }}" hx-swap="outerHTML">
        {% csrf_token %}
        <button class="btn--icon" type="submit" aria-label="Favorite">{% if recipe.is_favorite %}♥{% else %}♡{% endif %}</button>
      </form>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Run the suite — card contract must hold**

Run: `cd apps/web && pytest -q recipes/tests/test_pages.py`
Expected: PASS — in particular `test_list_favorite_returns_card` (asserts `href="/recipes/<id>/"` present) and the saved/favorites list tests (assert titles present) still pass against the new markup.

- [ ] **Step 4: Run the full suite**

Run: `cd apps/web && pytest -q`
Expected: PASS (same count as Task 1).

- [ ] **Step 5: Commit**

```bash
git add apps/web/static/css/components.css apps/web/templates/recipes/_recipe_card.html
git commit -m "feat(web): Mise component library CSS and video card"
```

---

## Task 3: User preference fields + constants

**Files:**
- Create: `apps/web/accounts/constants.py`, `apps/web/accounts/migrations/0002_user_preferences.py`
- Modify: `apps/web/accounts/models.py`
- Test: `apps/web/accounts/tests/test_onboarding.py`

**Interfaces:**
- Produces on `accounts.User`: `preferred_cuisines: list`, `dietary_tags: list`, `max_cook_time_minutes: int | None`, `onboarding_completed: bool`.
- Produces constants: `CUISINE_OPTIONS: list[str]`, `DIET_OPTIONS: list[str]`, `COOK_TIME_OPTIONS: list[tuple[int, str]]` (minutes, label; `0` means "Any").

- [ ] **Step 1: Write the failing model-defaults test**

Create `apps/web/accounts/tests/test_onboarding.py`:

```python
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_new_user_preference_defaults():
    u = User.objects.create_user(email="new@e.com", password="supersecret")
    assert u.preferred_cuisines == []
    assert u.dietary_tags == []
    assert u.max_cook_time_minutes is None
    assert u.onboarding_completed is False
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd apps/web && pytest -q accounts/tests/test_onboarding.py::test_new_user_preference_defaults`
Expected: FAIL with `AttributeError` (fields don't exist yet).

- [ ] **Step 3: Add the option constants**

Create `apps/web/accounts/constants.py`:

```python
# Shared option lists for onboarding preference selection. Single source of truth
# for both templates (render chips) and views (validate submitted values).

CUISINE_OPTIONS = [
    "Italian", "Mexican", "Thai", "Japanese", "Indian",
    "Chinese", "Korean", "French", "Mediterranean", "American",
]

DIET_OPTIONS = [
    "Vegetarian", "Vegan", "Gluten-free", "Dairy-free", "High-protein", "Low-carb",
]

# (minutes, label); 0 == no limit.
COOK_TIME_OPTIONS = [
    (15, "Under 15 min"),
    (30, "Under 30 min"),
    (45, "Under 45 min"),
    (60, "Under 1 hour"),
    (0, "Any length"),
]
```

- [ ] **Step 4: Add the model fields**

In `apps/web/accounts/models.py`, add these fields to `User` (after `date_joined`):

```python
    preferred_cuisines = models.JSONField(default=list, blank=True)
    dietary_tags = models.JSONField(default=list, blank=True)
    max_cook_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    onboarding_completed = models.BooleanField(default=False)
```

- [ ] **Step 5: Generate the migration**

Run: `cd apps/web && python manage.py makemigrations accounts`
Expected: creates `accounts/migrations/0002_user_preferences.py` adding the four fields. (If the auto name differs, rename the file to `0002_user_preferences.py` and keep its `dependencies = [("accounts", "0001_initial")]`.)

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd apps/web && pytest -q accounts/tests/test_onboarding.py::test_new_user_preference_defaults`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/web/accounts/constants.py apps/web/accounts/models.py apps/web/accounts/migrations/0002_user_preferences.py apps/web/accounts/tests/test_onboarding.py
git commit -m "feat(accounts): user taste-preference fields and option constants"
```

---

## Task 4: Onboarding entry — gating, signup redirect, welcome, skip

**Files:**
- Modify: `apps/web/accounts/views.py`, `apps/web/accounts/urls.py`, `apps/web/recipes/views.py`
- Create: `apps/web/templates/accounts/onboarding_welcome.html`
- Test: `apps/web/accounts/tests/test_onboarding.py`

**Interfaces:**
- Consumes: `User.onboarding_completed` (Task 3).
- Produces: url names `onboarding` (welcome, `/onboarding/`), `onboarding_skip` (`/onboarding/skip/`); decorator `onboarding_required(view)` in `accounts/views.py`.
- Produces: url names `onboarding_tastes`, `onboarding_cook_time` are added in Task 5; this task references only `onboarding` and `onboarding_skip`.

- [ ] **Step 1: Write failing redirect + gating + skip tests**

Append to `apps/web/accounts/tests/test_onboarding.py`:

```python
@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@e.com", password="supersecret")


@pytest.fixture
def auth_client(client, user):
    client.login(username="u@e.com", password="supersecret")
    return client


@pytest.mark.django_db
def test_signup_redirects_to_onboarding(client):
    resp = client.post(
        "/signup/",
        {"email": "cook@example.com", "display_name": "Cook", "password": "supersecret"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/onboarding/"


@pytest.mark.django_db
def test_incomplete_user_is_gated_to_onboarding(auth_client):
    resp = auth_client.get("/")  # discover
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/onboarding/"


@pytest.mark.django_db
def test_completed_user_reaches_discover(auth_client, user):
    user.onboarding_completed = True
    user.save(update_fields=["onboarding_completed"])
    resp = auth_client.get("/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_welcome_renders(auth_client):
    resp = auth_client.get("/onboarding/")
    assert resp.status_code == 200
    assert b"what are we cooking" in resp.content.lower() or b"cook" in resp.content.lower()


@pytest.mark.django_db
def test_skip_completes_with_empty_prefs(auth_client, user):
    resp = auth_client.post("/onboarding/skip/")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"
    user.refresh_from_db()
    assert user.onboarding_completed is True
    assert user.preferred_cuisines == []
    assert user.dietary_tags == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/web && pytest -q accounts/tests/test_onboarding.py`
Expected: FAIL (no `/onboarding/` route; discover not gated).

- [ ] **Step 3: Add the gating decorator + onboarding views**

In `apps/web/accounts/views.py`, add imports and code:

```python
from functools import wraps

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import SignupForm


def onboarding_required(view):
    """Redirect authenticated users who haven't finished onboarding into it."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.onboarding_completed:
            return redirect("onboarding")
        return view(request, *args, **kwargs)
    return wrapped
```

Change the `signup` view's success redirect from `return redirect("discover")` to:

```python
            return redirect("onboarding")
```

(There are two `redirect("discover")` calls in `signup` — the early `is_authenticated` guard at the top and the post-save one. Change ONLY the post-`form.save()`/`login()` one. Leave the top guard as `redirect("discover")`.)

Add the welcome + skip views at the end of the file:

```python
@login_required
def onboarding(request):
    if request.user.onboarding_completed:
        return redirect("discover")
    return render(request, "accounts/onboarding_welcome.html")


@login_required
@require_POST
def onboarding_skip(request):
    request.user.onboarding_completed = True
    request.user.save(update_fields=["onboarding_completed"])
    return redirect("discover")
```

- [ ] **Step 4: Register the onboarding routes**

In `apps/web/accounts/urls.py`, import the new views and add routes:

```python
from django.urls import path

from .views import (
    AppLoginView,
    AppLogoutView,
    onboarding,
    onboarding_skip,
    profile,
    signup,
)

urlpatterns = [
    path("login/", AppLoginView.as_view(), name="login"),
    path("logout/", AppLogoutView.as_view(), name="logout"),
    path("signup/", signup, name="signup"),
    path("profile/", profile, name="profile"),
    path("onboarding/", onboarding, name="onboarding"),
    path("onboarding/skip/", onboarding_skip, name="onboarding_skip"),
]
```

- [ ] **Step 5: Gate the authenticated content views**

In `apps/web/recipes/views.py`, import the decorator and apply it to `discover`, `saved`, and `favorites`. Add to the imports:

```python
from accounts.views import onboarding_required
```

Then stack the decorator directly under `@login_required` on each of those three view functions, e.g.:

```python
@login_required
@onboarding_required
def discover(request):
    return render(request, "recipes/discover.html")
```

Apply the same `@onboarding_required` (below `@login_required`) to `saved` and `favorites`.

- [ ] **Step 6: Create the welcome template**

Create `apps/web/templates/accounts/onboarding_welcome.html`:

```html
{% extends "base.html" %}
{% block title %}Welcome to Mise{% endblock %}
{% block content %}
<section class="wizard">
  <span class="wizard__eyebrow">Welcome</span>
  <h1 class="wizard__headline">Good to meet you — what are we cooking?</h1>
  <p class="wizard__lead">Tell us a little about your taste and we'll fill your feed with
    food videos that already have a recipe waiting. Takes about 20 seconds.</p>
  <div class="wizard__actions">
    <a class="btn btn--primary" href="{% url 'onboarding_tastes' %}">Get started</a>
    <form method="post" action="{% url 'onboarding_skip' %}">
      {% csrf_token %}
      <button class="btn btn--ghost" type="submit">Skip for now</button>
    </form>
  </div>
</section>
{% endblock %}
```

NOTE: this template references `{% url 'onboarding_tastes' %}`, added in Task 5. Until Task 5 lands, `test_welcome_renders` will error on the missing url. To keep this task independently green, temporarily point the "Get started" link at `{% url 'onboarding' %}` in this step, then switch it to `{% url 'onboarding_tastes' %}` in Task 5 Step 6. (The wizard CSS classes are styled in Task 5; unstyled render is acceptable here.)

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd apps/web && pytest -q accounts/tests/test_onboarding.py`
Expected: PASS (all five new tests + the defaults test).

- [ ] **Step 8: Run the full suite (existing signup test still 302s)**

Run: `cd apps/web && pytest -q`
Expected: PASS — `accounts/tests/test_auth.py::test_signup_creates_user_and_logs_in` still passes (asserts 302 only, destination unchecked).

- [ ] **Step 9: Commit**

```bash
git add apps/web/accounts/views.py apps/web/accounts/urls.py apps/web/recipes/views.py apps/web/templates/accounts/onboarding_welcome.html apps/web/accounts/tests/test_onboarding.py
git commit -m "feat(accounts): onboarding gating, signup redirect, welcome and skip"
```

---

## Task 5: Onboarding steps — tastes, cook time, finish + wizard styling

**Files:**
- Modify: `apps/web/accounts/views.py`, `apps/web/accounts/urls.py`, `apps/web/static/css/components.css`, `apps/web/templates/accounts/onboarding_welcome.html`
- Create: `apps/web/templates/accounts/onboarding_tastes.html`, `apps/web/templates/accounts/onboarding_cook_time.html`, `apps/web/templates/accounts/_onboarding_progress.html`
- Test: `apps/web/accounts/tests/test_onboarding.py`

**Interfaces:**
- Consumes: `onboarding_required`, url name `onboarding`, constants `CUISINE_OPTIONS`/`DIET_OPTIONS`/`COOK_TIME_OPTIONS`.
- Produces: url names `onboarding_tastes` (`/onboarding/tastes/`), `onboarding_cook_time` (`/onboarding/cook-time/`).
- Flow is stateless: step 2 (`onboarding_tastes`) persists cuisines + diet to the user then redirects to step 3 (`onboarding_cook_time`), which persists the cook-time limit, sets `onboarding_completed=True`, and redirects to `discover`.

- [ ] **Step 1: Write failing step tests**

Append to `apps/web/accounts/tests/test_onboarding.py`:

```python
@pytest.mark.django_db
def test_tastes_saves_and_advances(auth_client, user):
    resp = auth_client.post(
        "/onboarding/tastes/",
        {"cuisines": ["Italian", "Thai"], "diets": ["Vegetarian"]},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/onboarding/cook-time/"
    user.refresh_from_db()
    assert user.preferred_cuisines == ["Italian", "Thai"]
    assert user.dietary_tags == ["Vegetarian"]
    assert user.onboarding_completed is False  # not done until cook-time step


@pytest.mark.django_db
def test_tastes_ignores_unknown_values(auth_client, user):
    auth_client.post("/onboarding/tastes/", {"cuisines": ["Italian", "Klingon"]})
    user.refresh_from_db()
    assert user.preferred_cuisines == ["Italian"]


@pytest.mark.django_db
def test_cook_time_completes_onboarding(auth_client, user):
    resp = auth_client.post("/onboarding/cook-time/", {"max_cook_time": "30"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"
    user.refresh_from_db()
    assert user.max_cook_time_minutes == 30
    assert user.onboarding_completed is True


@pytest.mark.django_db
def test_cook_time_any_stores_null(auth_client, user):
    auth_client.post("/onboarding/cook-time/", {"max_cook_time": "0"})
    user.refresh_from_db()
    assert user.max_cook_time_minutes is None
    assert user.onboarding_completed is True
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/web && pytest -q accounts/tests/test_onboarding.py -k "tastes or cook_time"`
Expected: FAIL (routes don't exist).

- [ ] **Step 3: Add the step views**

In `apps/web/accounts/views.py`, add the constants import at the top:

```python
from .constants import COOK_TIME_OPTIONS, CUISINE_OPTIONS, DIET_OPTIONS
```

Add the two views:

```python
@login_required
@require_POST
def _noop():  # placeholder marker — do not include; see real views below
    pass
```

(Do NOT include the placeholder above — it is only here to mark where the real views go. Add exactly the following two views:)

```python
@login_required
def onboarding_tastes(request):
    if request.method == "POST":
        chosen_cuisines = [c for c in request.POST.getlist("cuisines") if c in CUISINE_OPTIONS]
        chosen_diets = [d for d in request.POST.getlist("diets") if d in DIET_OPTIONS]
        request.user.preferred_cuisines = chosen_cuisines
        request.user.dietary_tags = chosen_diets
        request.user.save(update_fields=["preferred_cuisines", "dietary_tags"])
        return redirect("onboarding_cook_time")
    return render(
        request,
        "accounts/onboarding_tastes.html",
        {
            "cuisine_options": CUISINE_OPTIONS,
            "diet_options": DIET_OPTIONS,
            "selected_cuisines": request.user.preferred_cuisines,
            "selected_diets": request.user.dietary_tags,
            "step": 2,
        },
    )


@login_required
def onboarding_cook_time(request):
    if request.method == "POST":
        valid = {str(m) for m, _ in COOK_TIME_OPTIONS}
        raw = request.POST.get("max_cook_time", "0")
        minutes = int(raw) if raw in valid else 0
        request.user.max_cook_time_minutes = minutes or None
        request.user.onboarding_completed = True
        request.user.save(update_fields=["max_cook_time_minutes", "onboarding_completed"])
        return redirect("discover")
    return render(
        request,
        "accounts/onboarding_cook_time.html",
        {"cook_time_options": COOK_TIME_OPTIONS, "step": 3},
    )
```

- [ ] **Step 4: Register the step routes**

In `apps/web/accounts/urls.py`, add the two views to the import list and two routes:

```python
from .views import (
    AppLoginView,
    AppLogoutView,
    onboarding,
    onboarding_cook_time,
    onboarding_skip,
    onboarding_tastes,
    profile,
    signup,
)
```

Add inside `urlpatterns` (after the `onboarding_skip` line):

```python
    path("onboarding/tastes/", onboarding_tastes, name="onboarding_tastes"),
    path("onboarding/cook-time/", onboarding_cook_time, name="onboarding_cook_time"),
```

- [ ] **Step 5: Create the progress partial and step templates**

Create `apps/web/templates/accounts/_onboarding_progress.html`:

```html
<div class="progress" aria-label="Step {{ step }} of 3">
  <span class="progress__dot {% if step >= 1 %}is-on{% endif %}"></span>
  <span class="progress__dot {% if step >= 2 %}is-on{% endif %}"></span>
  <span class="progress__dot {% if step >= 3 %}is-on{% endif %}"></span>
  <span class="progress__label">Step {{ step }} of 3</span>
</div>
```

Create `apps/web/templates/accounts/onboarding_tastes.html`:

```html
{% extends "base.html" %}
{% block title %}Your taste{% endblock %}
{% block content %}
<section class="wizard">
  {% include "accounts/_onboarding_progress.html" %}
  <h1 class="wizard__headline">What do you like to cook?</h1>
  <form method="post" class="wizard__form">
    {% csrf_token %}
    <p class="wizard__group-label">Cuisines</p>
    <div class="chip-grid">
      {% for c in cuisine_options %}
        <label class="chip">
          <input type="checkbox" name="cuisines" value="{{ c }}" {% if c in selected_cuisines %}checked{% endif %}>
          {{ c }}
        </label>
      {% endfor %}
    </div>
    <p class="wizard__group-label">Dietary preferences</p>
    <div class="chip-grid">
      {% for d in diet_options %}
        <label class="chip">
          <input type="checkbox" name="diets" value="{{ d }}" {% if d in selected_diets %}checked{% endif %}>
          {{ d }}
        </label>
      {% endfor %}
    </div>
    <div class="wizard__actions">
      <button class="btn btn--primary" type="submit">Continue</button>
    </div>
  </form>
</section>
{% endblock %}
```

Create `apps/web/templates/accounts/onboarding_cook_time.html`:

```html
{% extends "base.html" %}
{% block title %}Cook time{% endblock %}
{% block content %}
<section class="wizard">
  {% include "accounts/_onboarding_progress.html" %}
  <h1 class="wizard__headline">How much time do you usually have?</h1>
  <form method="post" class="wizard__form">
    {% csrf_token %}
    <div class="chip-grid">
      {% for minutes, label in cook_time_options %}
        <label class="chip">
          <input type="radio" name="max_cook_time" value="{{ minutes }}" {% if forloop.first %}checked{% endif %}>
          {{ label }}
        </label>
      {% endfor %}
    </div>
    <div class="wizard__actions">
      <button class="btn btn--primary" type="submit">Finish</button>
    </div>
  </form>
</section>
{% endblock %}
```

- [ ] **Step 6: Point the welcome CTA at the first step**

In `apps/web/templates/accounts/onboarding_welcome.html`, change the "Get started" link from `{% url 'onboarding' %}` (the Task 4 placeholder) to:

```html
    <a class="btn btn--primary" href="{% url 'onboarding_tastes' %}">Get started</a>
```

- [ ] **Step 7: Add wizard + progress + chip-grid styling**

Append to `apps/web/static/css/components.css`:

```css
/* onboarding wizard */
.wizard { max-width: 640px; margin: 40px auto; }
.wizard__eyebrow { font-family: var(--font-mono); font-size: 12px; letter-spacing: .18em; text-transform: uppercase; color: var(--accent); }
.wizard__headline { font-family: var(--font-display); font-weight: 500; font-size: 40px; line-height: 1.06; letter-spacing: -.01em; margin: 14px 0 12px; color: var(--ink); }
.wizard__lead { max-width: 520px; font-size: 16px; line-height: 1.6; color: var(--ink-2); }
.wizard__group-label { font-family: var(--font-mono); font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); margin: 26px 0 12px; }
.wizard__form { margin-top: 20px; }
.wizard__actions { display: flex; align-items: center; gap: 14px; margin-top: 32px; }
.chip-grid { display: flex; flex-wrap: wrap; gap: 9px; }

.progress { display: flex; align-items: center; gap: 8px; margin-bottom: 24px; }
.progress__dot { width: 9px; height: 9px; border-radius: 50%; background: var(--surface-2); border: 1px solid var(--line-2); }
.progress__dot.is-on { background: var(--accent); border-color: var(--accent); }
.progress__label { font-family: var(--font-mono); font-size: 11.5px; color: var(--muted); margin-left: 6px; }
```

- [ ] **Step 8: Run the onboarding tests**

Run: `cd apps/web && pytest -q accounts/tests/test_onboarding.py`
Expected: PASS (all tests including the new step tests).

- [ ] **Step 9: Run the full suite**

Run: `cd apps/web && pytest -q`
Expected: PASS (no regressions).

- [ ] **Step 10: Commit**

```bash
git add apps/web/accounts/views.py apps/web/accounts/urls.py apps/web/static/css/components.css apps/web/templates/accounts/onboarding_tastes.html apps/web/templates/accounts/onboarding_cook_time.html apps/web/templates/accounts/_onboarding_progress.html apps/web/templates/accounts/onboarding_welcome.html apps/web/accounts/tests/test_onboarding.py
git commit -m "feat(accounts): taste + cook-time onboarding steps with wizard styling"
```

---

## Self-Review

**Spec coverage:**
- CSS foundation + static setup → Task 1. ✅
- Full component class library (buttons, chips, badges, inputs, video card, ingredient/step/extraction primitives) → Task 2. ✅
- Shell restyle + recipe-card uses video card → Tasks 1 & 2. ✅
- User preference fields + migration + shared option constants → Task 3. ✅
- 3-step wizard, progress, gating, signup redirect, skip, stateless per-step save → Tasks 4 & 5. ✅
- Tests (defaults, signup redirect, gating, complete saves prefs + flag, skip) → Tasks 3–5. ✅
- Out of scope (per-screen rebuilds, palette switcher, recommendation logic) → not planned, matches spec. ✅

**Note on spec refinement:** the spec said step state is carried in the POST; this plan persists each step to the user row instead (simpler, fully stateless, no hidden fields). Same observable behavior; called out here intentionally.

**Placeholder scan:** No TBD/TODO. The one `_noop` marker in Task 5 Step 3 is explicitly labeled "do not include" with the real views shown immediately below. ✅

**Type/name consistency:** url names (`onboarding`, `onboarding_skip`, `onboarding_tastes`, `onboarding_cook_time`), decorator `onboarding_required`, constants (`CUISINE_OPTIONS`, `DIET_OPTIONS`, `COOK_TIME_OPTIONS`), and field names (`preferred_cuisines`, `dietary_tags`, `max_cook_time_minutes`, `onboarding_completed`) are used identically across tasks. Cross-task ordering: welcome CTA placeholder in Task 4 → real `onboarding_tastes` url in Task 5 (called out in both). ✅
