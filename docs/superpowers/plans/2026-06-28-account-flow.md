# Account & Onboarding Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the sign-in / create-account screens to the Mise split-panel design, wire real password reset with Mise-styled templates, and add a standalone verify-email preview — all per `mise/Account Flow.dc.html`.

**Architecture:** Django templates extending a new minimal `base_auth.html` (no app-bar, full-height) and reusing the existing `tokens.css` / `components.css` system. A small set of new `.auth-*` classes carry the split-panel and single-card layouts. Password reset uses Django's built-in `django.contrib.auth.views`. Google sign-in and email-code verification are non-functional placeholders rendered per design.

**Tech Stack:** Django 5, server-rendered templates, plain CSS custom properties, pytest + pytest-django.

## Global Constraints

- **No new dependencies.** Use only Django built-ins and the existing CSS system.
- **Reuse tokens/components.** Style with `var(--*)` tokens from `tokens.css` and existing classes (`.btn`, `.btn--primary`, `.text-input`, `.flash`) before adding new ones.
- **Spec:** `docs/superpowers/specs/2026-06-28-account-flow-design.md`.
- **Branch:** `feat/mise-account-flow` (already created off `origin/main`; the design spec is already committed there).
- **Test command (run from `apps/web/`):** `../../.venv-web/bin/pytest <path> -q`
- **Placeholders honesty:** "Continue with Google" is always `disabled` with a "SOON" affordance; the verify-email screen is preview-only and never inserted into the live signup flow (signup still redirects to `onboarding`).
- **Mise copy** (use verbatim): sign-in brand tag `WELCOME BACK`, headline "Your kitchen is waiting."; create-account brand tag `JOIN MISE`, headline "Every recipe worth keeping."
- **Commit** after each task. End commit messages with:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## File Structure

- `design/mise/Account Flow.dc.html` (create) — imported design reference
- `design/mise/Account Creation.dc.html` (create) — imported design reference
- `apps/web/templates/base_auth.html` (create) — minimal auth page shell
- `apps/web/templates/accounts/login.html` (modify) — split-panel sign in
- `apps/web/templates/accounts/signup.html` (modify) — split-panel create account
- `apps/web/templates/accounts/verify_email.html` (create) — preview screen
- `apps/web/templates/accounts/password_reset_form.html` (create)
- `apps/web/templates/accounts/password_reset_done.html` (create)
- `apps/web/templates/accounts/password_reset_confirm.html` (create)
- `apps/web/templates/accounts/password_reset_complete.html` (create)
- `apps/web/templates/accounts/password_reset_email.txt` (create)
- `apps/web/templates/accounts/password_reset_subject.txt` (create)
- `apps/web/accounts/forms.py` (modify) — drop `display_name` from signup form
- `apps/web/accounts/views.py` (modify) — add `verify_email` view
- `apps/web/accounts/urls.py` (modify) — add verify-email + 4 reset routes
- `apps/web/static/css/components.css` (modify) — add `.auth-*` classes
- `apps/web/config/settings.py` (modify) — email backend + from-address
- `.env.example` (modify) — document the email env vars
- `apps/web/accounts/tests/test_password_reset.py` (create) — reset flow tests
- `apps/web/accounts/tests/test_account_flow.py` (create) — smoke GET tests
- `apps/web/accounts/tests/test_auth.py` (modify) — add no-display-name signup test

---

### Task 1: Import design source

**Files:**
- Create: `design/mise/Account Flow.dc.html`
- Create: `design/mise/Account Creation.dc.html`

**Interfaces:**
- Consumes: nothing
- Produces: reference docs only (not served, not imported by code)

- [ ] **Step 1: Fetch and write the two design docs via the Claude Design MCP**

Use the `DesignSync` tool, `method: "get_file"`, `projectId: "08c47bb6-766a-4a23-b6e5-6e3899349d3d"`, once per path:
- `mise/Account Flow.dc.html` → write to `design/mise/Account Flow.dc.html`
- `mise/Account Creation.dc.html` → write to `design/mise/Account Creation.dc.html`

(Create the `design/mise/` directory. These are read-only reference copies — do not edit them.)

- [ ] **Step 2: Verify the files exist and are non-empty**

Run: `wc -l "design/mise/Account Flow.dc.html" "design/mise/Account Creation.dc.html"`
Expected: both files listed with a non-zero line count.

- [ ] **Step 3: Commit**

```bash
git add "design/mise/Account Flow.dc.html" "design/mise/Account Creation.dc.html"
git commit -m "docs(design): import Mise account flow source

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Drop `display_name` from the signup form

**Files:**
- Modify: `apps/web/accounts/forms.py`
- Test: `apps/web/accounts/tests/test_auth.py`

**Interfaces:**
- Consumes: existing `SignupForm` (ModelForm over `accounts.User`, custom `password` field)
- Produces: `SignupForm` with rendered fields `email` + `password` only. `display_name` stays on the model (default `""`), still editable on the profile page.

- [ ] **Step 1: Write the failing test**

Add to `apps/web/accounts/tests/test_auth.py`:

```python
@pytest.mark.django_db
def test_signup_does_not_require_display_name(client):
    resp = client.post(
        "/signup/", {"email": "no-name@example.com", "password": "supersecret"}
    )
    assert resp.status_code == 302
    u = User.objects.get(email="no-name@example.com")
    assert u.check_password("supersecret")
    assert u.display_name == ""
    assert "display_name" not in SignupForm().fields
```

Add the import at the top of the file (keep the existing imports):

```python
from accounts.forms import SignupForm
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../.venv-web/bin/pytest accounts/tests/test_auth.py::test_signup_does_not_require_display_name -q`
Expected: FAIL — `'display_name' in SignupForm().fields` (assertion error).

- [ ] **Step 3: Make the change**

In `apps/web/accounts/forms.py`, change the `Meta.fields` list:

```python
    class Meta:
        model = User
        fields = ["email"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `../../.venv-web/bin/pytest accounts/tests/test_auth.py -q`
Expected: PASS (all auth tests, including the existing `test_signup_creates_user_and_logs_in` which posts a stray `display_name` that is now ignored).

- [ ] **Step 5: Commit**

```bash
git add apps/web/accounts/forms.py apps/web/accounts/tests/test_auth.py
git commit -m "feat(accounts): drop display_name from signup form

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Auth shell + verify-email preview

Establishes `base_auth.html` and the single-card CSS, proven via the standalone verify-email screen (no other URLs needed).

**Files:**
- Create: `apps/web/templates/base_auth.html`
- Create: `apps/web/templates/accounts/verify_email.html`
- Modify: `apps/web/static/css/components.css`
- Modify: `apps/web/accounts/views.py`
- Modify: `apps/web/accounts/urls.py`
- Test: `apps/web/accounts/tests/test_account_flow.py`

**Interfaces:**
- Consumes: `tokens.css`, `components.css`, fonts (loaded in the shell)
- Produces:
  - `base_auth.html` — base template with `{% block title %}` and `{% block content %}`, body `<main class="auth-page">`.
  - URL name `verify_email` at `/verify-email/`.
  - View `verify_email(request)` rendering `accounts/verify_email.html`.
  - CSS classes: `.auth-page`, `.auth-card`, `.auth-card__title`, `.auth-card__sub`, `.auth-label`, `.auth-field`, `.auth-error`, `.auth-foot`, `.auth-divider`, `.auth-icon`, `.btn--block`, `.btn--social`, `.code-input`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/accounts/tests/test_account_flow.py`:

```python
import pytest


@pytest.mark.django_db
def test_verify_email_preview_renders(client):
    resp = client.get("/verify-email/")
    assert resp.status_code == 200
    assert b"Verify your email" in resp.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../.venv-web/bin/pytest accounts/tests/test_account_flow.py -q`
Expected: FAIL — 404 (no `/verify-email/` route yet).

- [ ] **Step 3: Create `apps/web/templates/base_auth.html`**

```html
{% load static %}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Mise{% endblock %}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300..600;1,6..72,300..500&family=Hanken+Grotesk:wght@400;500;600;700;800&family=Spline+Sans+Mono:wght@400;500;600&display=swap">
  <link rel="stylesheet" href="{% static 'css/tokens.css' %}">
  <link rel="stylesheet" href="{% static 'css/components.css' %}">
</head>
<body>
  <main class="auth-page">
    {% if messages %}<ul class="flash">{% for m in messages %}<li>{{ m }}</li>{% endfor %}</ul>{% endif %}
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 4: Append the single-card auth CSS to `apps/web/static/css/components.css`**

```css

/* auth — account flow (single-card screens: verify, password reset) */
.auth-page { min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 32px; }
.auth-page .flash { position: absolute; top: 0; left: 0; right: 0; }
.auth-card {
  width: 100%; max-width: 460px; background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-xl); box-shadow: var(--shadow-2); padding: 36px 38px; box-sizing: border-box;
}
.auth-card__title { font-family: var(--font-display); font-weight: 500; font-size: 26px; letter-spacing: -.01em; color: var(--ink); margin: 0 0 6px; }
.auth-card__sub { font-size: 14px; line-height: 1.5; color: var(--ink-2); margin: 0 0 22px; }
.auth-label { font-family: var(--font-mono); font-size: 10.5px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; display: block; }
.auth-field { margin-bottom: 16px; }
.auth-error { font-size: 12.5px; color: var(--accent); margin-top: 6px; }
.auth-foot { margin-top: 20px; text-align: center; font-size: 13.5px; color: var(--muted); }
.auth-foot a { font-weight: 600; }
.auth-divider { display: flex; align-items: center; gap: 12px; margin: 18px 0; }
.auth-divider::before, .auth-divider::after { content: ""; flex: 1; height: 1px; background: var(--line); }
.auth-divider span { font-family: var(--font-mono); font-size: 10px; letter-spacing: .12em; color: var(--muted); }
.auth-icon { width: 54px; height: 54px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); display: flex; align-items: center; justify-content: center; margin-bottom: 18px; }
.btn--block { width: 100%; justify-content: center; }
.btn--social { background: var(--surface); color: var(--ink); border: 1px solid var(--line-2); box-shadow: none; }
.btn--social:hover { background: var(--surface-2); }
.btn--social:disabled { background: var(--surface); color: var(--ink-2); cursor: not-allowed; }
.btn--social .coming-soon { font-family: var(--font-mono); font-size: 9px; letter-spacing: .1em; color: var(--muted); margin-left: auto; }
.code-input { display: flex; gap: 9px; margin: 8px 0 20px; }
.code-input span {
  flex: 1; height: 56px; border: 1px solid var(--line-2); border-radius: var(--r-md); background: var(--paper);
  display: flex; align-items: center; justify-content: center; font-family: var(--font-mono); font-size: 22px; color: var(--ink);
}
.code-input span.is-filled { border-color: var(--accent-line); }
```

- [ ] **Step 5: Create `apps/web/templates/accounts/verify_email.html`**

```html
{% extends "base_auth.html" %}
{% comment %}Preview-only screen — not wired into signup. See the account-flow spec.{% endcomment %}
{% block title %}Verify your email{% endblock %}
{% block content %}
<div class="auth-card" data-screen-label="Verify email">
  <div class="auth-card__title">Verify your email</div>
  <p class="auth-card__sub">We sent a 6-digit code to <strong style="color:var(--ink);">you@example.com</strong>. Enter it below to confirm it's you.</p>
  <div class="code-input" aria-hidden="true">
    <span class="is-filled">4</span><span class="is-filled">8</span><span></span><span></span><span></span><span></span>
  </div>
  <button class="btn btn--primary btn--block" type="button" disabled>Verify email</button>
  <p class="auth-foot"><span style="color:var(--accent);font-weight:600;">Resend code</span> &nbsp;·&nbsp; <span style="color:var(--accent);font-weight:600;">Change email</span></p>
</div>
{% endblock %}
```

- [ ] **Step 6: Add the `verify_email` view to `apps/web/accounts/views.py`**

Add at the end of the file:

```python
def verify_email(request):
    """Standalone styled preview of the email-verification screen.

    Not wired into signup (see the account-flow spec) — renders only.
    """
    return render(request, "accounts/verify_email.html")
```

- [ ] **Step 7: Wire the route in `apps/web/accounts/urls.py`**

Add `verify_email` to the import block:

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
    verify_email,
)
```

Add this entry to `urlpatterns`:

```python
    path("verify-email/", verify_email, name="verify_email"),
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `../../.venv-web/bin/pytest accounts/tests/test_account_flow.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add apps/web/templates/base_auth.html apps/web/templates/accounts/verify_email.html apps/web/static/css/components.css apps/web/accounts/views.py apps/web/accounts/urls.py apps/web/accounts/tests/test_account_flow.py
git commit -m "feat(accounts): auth shell + verify-email preview screen

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Password reset flow (real)

**Files:**
- Create: `apps/web/templates/accounts/password_reset_form.html`
- Create: `apps/web/templates/accounts/password_reset_done.html`
- Create: `apps/web/templates/accounts/password_reset_confirm.html`
- Create: `apps/web/templates/accounts/password_reset_complete.html`
- Create: `apps/web/templates/accounts/password_reset_email.txt`
- Create: `apps/web/templates/accounts/password_reset_subject.txt`
- Modify: `apps/web/accounts/urls.py`
- Modify: `apps/web/config/settings.py`
- Modify: `.env.example`
- Test: `apps/web/accounts/tests/test_password_reset.py`

**Interfaces:**
- Consumes: `base_auth.html` and the `.auth-card` CSS from Task 3; Django's `django.contrib.auth.views`.
- Produces: URL names `password_reset`, `password_reset_done`, `password_reset_confirm`, `password_reset_complete`. Reset emails delivered via the configured backend (locmem in tests).

- [ ] **Step 1: Write the failing tests**

Create `apps/web/accounts/tests/test_password_reset.py`:

```python
import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail

User = get_user_model()


@pytest.mark.django_db
def test_reset_form_get_renders(client):
    resp = client.get("/password-reset/")
    assert resp.status_code == 200
    assert b"Reset your password" in resp.content


@pytest.mark.django_db
def test_password_reset_emails_a_working_link(client):
    User.objects.create_user(email="cook@example.com", password="oldpassword1")

    resp = client.post("/password-reset/", {"email": "cook@example.com"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/password-reset/done/"

    assert len(mail.outbox) == 1
    body = mail.outbox[0].body
    match = re.search(r"/reset/[^/\s]+/[^/\s]+/", body)
    assert match, body
    link = match.group(0)

    # GET the link -> view stashes the token in the session and redirects
    # to the set-password URL.
    resp = client.get(link)
    assert resp.status_code == 302
    set_url = resp.headers["Location"]

    resp = client.post(
        set_url,
        {"new_password1": "brandnew-pass9", "new_password2": "brandnew-pass9"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/reset/done/"

    user = User.objects.get(email="cook@example.com")
    assert user.check_password("brandnew-pass9")


@pytest.mark.django_db
def test_reset_unknown_email_shows_done_without_sending(client):
    resp = client.post("/password-reset/", {"email": "nobody@example.com"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/password-reset/done/"
    assert len(mail.outbox) == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `../../.venv-web/bin/pytest accounts/tests/test_password_reset.py -q`
Expected: FAIL — 404 on `/password-reset/` (routes not added yet).

- [ ] **Step 3: Add the reset routes to `apps/web/accounts/urls.py`**

Replace the import line `from django.urls import path` with:

```python
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
```

Add these four entries to `urlpatterns`:

```python
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
```

- [ ] **Step 4: Create `apps/web/templates/accounts/password_reset_form.html`**

```html
{% extends "base_auth.html" %}
{% block title %}Reset your password{% endblock %}
{% block content %}
<div class="auth-card" data-screen-label="Reset password">
  <div class="auth-card__title">Reset your password</div>
  <p class="auth-card__sub">Enter the email you signed up with and we'll send you a link to set a new password.</p>
  <form method="post">
    {% csrf_token %}
    <div class="auth-field">
      <label class="auth-label" for="id_email">Email</label>
      <input class="text-input" type="email" name="email" id="id_email" autocomplete="email" placeholder="you@example.com" value="{{ form.email.value|default:'' }}" required>
      {% if form.email.errors %}<div class="auth-error">{{ form.email.errors|striptags }}</div>{% endif %}
    </div>
    <button class="btn btn--primary btn--block" type="submit">Send reset link</button>
  </form>
  <p class="auth-foot"><a href="{% url 'login' %}">← Back to sign in</a></p>
</div>
{% endblock %}
```

- [ ] **Step 5: Create `apps/web/templates/accounts/password_reset_done.html`**

```html
{% extends "base_auth.html" %}
{% block title %}Check your inbox{% endblock %}
{% block content %}
<div class="auth-card" data-screen-label="Check your inbox">
  <div class="auth-icon">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"></rect><path d="m22 7-10 6L2 7"></path></svg>
  </div>
  <div class="auth-card__title">Check your inbox</div>
  <p class="auth-card__sub">If an account exists for that address, we've emailed a link to reset your password. It may take a few minutes to arrive.</p>
  <p class="auth-foot"><a href="{% url 'login' %}">← Back to sign in</a></p>
</div>
{% endblock %}
```

- [ ] **Step 6: Create `apps/web/templates/accounts/password_reset_confirm.html`**

```html
{% extends "base_auth.html" %}
{% block title %}Set a new password{% endblock %}
{% block content %}
<div class="auth-card" data-screen-label="Set a new password">
  {% if validlink %}
  <div class="auth-card__title">Set a new password</div>
  <p class="auth-card__sub">Choose a new password for your account.</p>
  <form method="post">
    {% csrf_token %}
    <div class="auth-field">
      <label class="auth-label" for="id_new_password1">New password</label>
      <input class="text-input" type="password" name="new_password1" id="id_new_password1" autocomplete="new-password" required>
      {% if form.new_password1.errors %}<div class="auth-error">{{ form.new_password1.errors|striptags }}</div>{% endif %}
    </div>
    <div class="auth-field">
      <label class="auth-label" for="id_new_password2">Confirm password</label>
      <input class="text-input" type="password" name="new_password2" id="id_new_password2" autocomplete="new-password" required>
      {% if form.new_password2.errors %}<div class="auth-error">{{ form.new_password2.errors|striptags }}</div>{% endif %}
    </div>
    <button class="btn btn--primary btn--block" type="submit">Update password</button>
  </form>
  {% else %}
  <div class="auth-card__title">Link expired</div>
  <p class="auth-card__sub">This password reset link is invalid or has already been used. Request a new one to continue.</p>
  <p class="auth-foot"><a href="{% url 'password_reset' %}">Request a new link</a></p>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 7: Create `apps/web/templates/accounts/password_reset_complete.html`**

```html
{% extends "base_auth.html" %}
{% block title %}Password updated{% endblock %}
{% block content %}
<div class="auth-card" data-screen-label="Password updated">
  <div class="auth-icon">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
  </div>
  <div class="auth-card__title">Password updated</div>
  <p class="auth-card__sub">Your password has been changed. You can now sign in with your new password.</p>
  <a class="btn btn--primary btn--block" href="{% url 'login' %}">Back to sign in</a>
</div>
{% endblock %}
```

- [ ] **Step 8: Create `apps/web/templates/accounts/password_reset_email.txt`**

```
{% autoescape off %}Hi,

We received a request to reset the password for your Mise account. Open the link
below to choose a new password:

{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' uidb64=uid token=token %}

If you didn't request this, you can safely ignore this email — your password
won't change.

— Mise
{% endautoescape %}
```

- [ ] **Step 9: Create `apps/web/templates/accounts/password_reset_subject.txt`**

```
Reset your Mise password
```

(Single line. Django strips newlines from the subject template.)

- [ ] **Step 10: Add email settings to `apps/web/config/settings.py`**

Immediately after the `LOGIN_REDIRECT_URL = "discover"` line, add:

```python

# Email — console backend by default so dev (and password reset) works with no
# secrets and never silently fails to an unconfigured SMTP server. Override in
# production via DJANGO_EMAIL_BACKEND + the standard EMAIL_* settings.
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.environ.get(
    "DJANGO_DEFAULT_FROM_EMAIL", "Mise <no-reply@mise.local>"
)
```

(Confirm `import os` is already at the top of `settings.py` — it is, since `DEBUG` reads `os.environ`.)

- [ ] **Step 11: Document the env vars in `.env.example`**

Append:

```
# Email (password reset). Console backend prints emails to the server log in dev;
# set a real backend + SMTP credentials for actual delivery in production.
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DJANGO_DEFAULT_FROM_EMAIL=Mise <no-reply@mise.local>
```

- [ ] **Step 12: Run the tests to verify they pass**

Run: `../../.venv-web/bin/pytest accounts/tests/test_password_reset.py -q`
Expected: PASS (3 tests). (pytest-django uses the locmem email backend, so `mail.outbox` is populated regardless of `EMAIL_BACKEND`.)

- [ ] **Step 13: Commit**

```bash
git add apps/web/templates/accounts/password_reset_*.html apps/web/templates/accounts/password_reset_*.txt apps/web/accounts/urls.py apps/web/config/settings.py .env.example apps/web/accounts/tests/test_password_reset.py
git commit -m "feat(accounts): password reset flow with Mise templates

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Sign in restyle (split-panel)

**Files:**
- Modify: `apps/web/static/css/components.css`
- Modify: `apps/web/templates/accounts/login.html`
- Test: `apps/web/accounts/tests/test_account_flow.py`

**Interfaces:**
- Consumes: `base_auth.html` (Task 3); URL names `password_reset` (Task 4) and `signup`; `AppLoginView` passing Django's `AuthenticationForm` (fields `username` = email, `password`).
- Produces: CSS classes `.auth-split`, `.auth-brand`, `.auth-brand__logo/__tag/__head/__copy/__perks`, `.auth-formpanel`. Restyled `/login/`.

- [ ] **Step 1: Write the failing test**

Add to `apps/web/accounts/tests/test_account_flow.py`:

```python
@pytest.mark.django_db
def test_login_page_renders_styled(client):
    resp = client.get("/login/")
    assert resp.status_code == 200
    assert b"Continue with Google" in resp.content
    assert b"Forgot" in resp.content
    assert b"Create an account" in resp.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../.venv-web/bin/pytest accounts/tests/test_account_flow.py::test_login_page_renders_styled -q`
Expected: FAIL — current `login.html` has none of that copy.

- [ ] **Step 3: Append the split-panel CSS to `apps/web/static/css/components.css`**

```css

/* auth — split-panel (sign in / create account) */
.auth-split {
  width: 100%; max-width: 940px; background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-xl); box-shadow: var(--shadow-2); overflow: hidden;
  display: grid; grid-template-columns: 0.82fr 1.18fr;
}
.auth-brand { background: var(--accent); color: var(--on-accent); padding: 40px 38px; display: flex; flex-direction: column; justify-content: space-between; gap: 34px; }
.auth-brand__logo { font-family: var(--font-display); font-weight: 560; font-size: 26px; letter-spacing: -.01em; }
.auth-brand__tag { font-family: var(--font-mono); font-size: 11px; letter-spacing: .16em; opacity: .85; }
.auth-brand__head { font-family: var(--font-display); font-weight: 400; font-size: 34px; line-height: 1.07; letter-spacing: -.015em; margin: 12px 0 14px; }
.auth-brand__copy { margin: 0; font-size: 14.5px; line-height: 1.6; opacity: .9; }
.auth-brand__perks { display: flex; flex-direction: column; gap: 12px; list-style: none; padding: 0; margin: 0; }
.auth-brand__perks li { display: flex; align-items: center; gap: 11px; font-size: 13.5px; opacity: .94; }
.auth-brand__perks svg { flex: 0 0 auto; width: 22px; height: 22px; border-radius: 999px; background: rgba(255,255,255,.18); padding: 5px; box-sizing: border-box; }
.auth-formpanel { padding: 40px 42px; display: flex; flex-direction: column; }
@media (max-width: 720px) {
  .auth-split { grid-template-columns: 1fr; max-width: 460px; }
  .auth-brand { display: none; }
  .auth-formpanel { padding: 36px 30px; }
}
```

- [ ] **Step 4: Replace `apps/web/templates/accounts/login.html`**

```html
{% extends "base_auth.html" %}
{% block title %}Sign in{% endblock %}
{% block content %}
<div class="auth-split" data-screen-label="Sign in">
  <aside class="auth-brand">
    <span class="auth-brand__logo">Mise</span>
    <div>
      <span class="auth-brand__tag">WELCOME BACK</span>
      <h2 class="auth-brand__head">Your kitchen<br>is waiting.</h2>
      <p class="auth-brand__copy">Sign back in to pick up your feed, your saved recipes, and your collections — right where you left them.</p>
    </div>
    <ul class="auth-brand__perks">
      <li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Your saved recipes, synced</li>
      <li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Pick up mid-recipe, any device</li>
      <li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Your taste, already tuned</li>
    </ul>
  </aside>
  <div class="auth-formpanel">
    <h1 class="auth-card__title">Sign in</h1>
    <p class="auth-card__sub">Good to see you back in the kitchen.</p>

    <button class="btn btn--social btn--block" type="button" disabled aria-label="Continue with Google (coming soon)">
      <svg width="17" height="17" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.4 29.2 35.5 24 35.5c-6.4 0-11.5-5.1-11.5-11.5S17.6 12.5 24 12.5c2.9 0 5.6 1.1 7.6 2.9l5.7-5.7C33.6 6.2 29.1 4.5 24 4.5 13.2 4.5 4.5 13.2 4.5 24S13.2 43.5 24 43.5c10.7 0 19.5-8.7 19.5-19.5 0-1.2-.1-2.3-.4-3.5z"/><path fill="#FF3D00" d="M6.8 14.7l6.6 4.8C15.2 15.1 19.2 12.5 24 12.5c2.9 0 5.6 1.1 7.6 2.9l5.7-5.7C33.6 6.2 29.1 4.5 24 4.5c-7.3 0-13.7 4.1-16.9 10.2z"/><path fill="#4CAF50" d="M24 43.5c5.1 0 9.5-1.7 12.9-4.6l-6.2-5c-1.9 1.4-4.3 2.1-6.7 2.1-5.2 0-9.6-3.1-11.3-7.5l-6.5 5C9.4 39.3 16 43.5 24 43.5z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.2-4.2 5.5l6.2 5c-.4.4 6.7-4.9 6.7-14.5 0-1.2-.1-2.3-.4-3.5z"/></svg>
      Continue with Google <span class="coming-soon">SOON</span>
    </button>
    <div class="auth-divider"><span>OR</span></div>

    <form method="post">
      {% csrf_token %}
      {% if form.non_field_errors %}<div class="auth-error" style="margin-bottom:14px;">{{ form.non_field_errors|striptags }}</div>{% endif %}
      <div class="auth-field">
        <label class="auth-label" for="id_username">Email</label>
        <input class="text-input" type="email" name="username" id="id_username" autocomplete="email" placeholder="you@example.com" value="{{ form.username.value|default:'' }}" required>
      </div>
      <div class="auth-field">
        <div style="display:flex; justify-content:space-between; align-items:baseline;">
          <label class="auth-label" for="id_password">Password</label>
          <a class="auth-label" style="color:var(--accent);" href="{% url 'password_reset' %}">Forgot?</a>
        </div>
        <input class="text-input" type="password" name="password" id="id_password" autocomplete="current-password" required>
      </div>
      <button class="btn btn--primary btn--block" type="submit">Sign in</button>
    </form>
    <p class="auth-foot">New to Mise? <a href="{% url 'signup' %}">Create an account</a></p>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `../../.venv-web/bin/pytest accounts/tests/test_account_flow.py accounts/tests/test_auth.py -q`
Expected: PASS — the new smoke test plus the existing `test_login_with_email` (POSTs `username`/`password`, still works).

- [ ] **Step 6: Commit**

```bash
git add apps/web/static/css/components.css apps/web/templates/accounts/login.html apps/web/accounts/tests/test_account_flow.py
git commit -m "feat(accounts): restyle sign in to Mise split-panel

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Create account restyle (split-panel)

**Files:**
- Modify: `apps/web/templates/accounts/signup.html`
- Test: `apps/web/accounts/tests/test_account_flow.py`

**Interfaces:**
- Consumes: `base_auth.html` (Task 3); `.auth-split` CSS (Task 5); `SignupForm` with fields `email` + `password` (Task 2); URL name `login`.
- Produces: restyled `/signup/`.

- [ ] **Step 1: Write the failing test**

Add to `apps/web/accounts/tests/test_account_flow.py`:

```python
@pytest.mark.django_db
def test_signup_page_renders_styled(client):
    resp = client.get("/signup/")
    assert resp.status_code == 200
    assert b"Create your account" in resp.content
    assert b"Continue with Google" in resp.content
    assert b"Already have an account" in resp.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../.venv-web/bin/pytest accounts/tests/test_account_flow.py::test_signup_page_renders_styled -q`
Expected: FAIL — current `signup.html` lacks that copy.

- [ ] **Step 3: Replace `apps/web/templates/accounts/signup.html`**

```html
{% extends "base_auth.html" %}
{% block title %}Create your account{% endblock %}
{% block content %}
<div class="auth-split" data-screen-label="Create account">
  <aside class="auth-brand">
    <span class="auth-brand__logo">Mise</span>
    <div>
      <span class="auth-brand__tag">JOIN MISE</span>
      <h2 class="auth-brand__head">Every recipe<br>worth keeping.</h2>
      <p class="auth-brand__copy">Make a free account to save recipes from any YouTube video and build a cookbook that cooks the way you do.</p>
    </div>
    <ul class="auth-brand__perks">
      <li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Save recipes from any video</li>
      <li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Steps linked to the exact moment</li>
      <li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Collections, organised your way</li>
    </ul>
  </aside>
  <div class="auth-formpanel">
    <h1 class="auth-card__title">Create your account</h1>
    <p class="auth-card__sub">Free forever — no card needed.</p>

    <button class="btn btn--social btn--block" type="button" disabled aria-label="Continue with Google (coming soon)">
      <svg width="17" height="17" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.4 29.2 35.5 24 35.5c-6.4 0-11.5-5.1-11.5-11.5S17.6 12.5 24 12.5c2.9 0 5.6 1.1 7.6 2.9l5.7-5.7C33.6 6.2 29.1 4.5 24 4.5 13.2 4.5 4.5 13.2 4.5 24S13.2 43.5 24 43.5c10.7 0 19.5-8.7 19.5-19.5 0-1.2-.1-2.3-.4-3.5z"/><path fill="#FF3D00" d="M6.8 14.7l6.6 4.8C15.2 15.1 19.2 12.5 24 12.5c2.9 0 5.6 1.1 7.6 2.9l5.7-5.7C33.6 6.2 29.1 4.5 24 4.5c-7.3 0-13.7 4.1-16.9 10.2z"/><path fill="#4CAF50" d="M24 43.5c5.1 0 9.5-1.7 12.9-4.6l-6.2-5c-1.9 1.4-4.3 2.1-6.7 2.1-5.2 0-9.6-3.1-11.3-7.5l-6.5 5C9.4 39.3 16 43.5 24 43.5z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.2-4.2 5.5l6.2 5c-.4.4 6.7-4.9 6.7-14.5 0-1.2-.1-2.3-.4-3.5z"/></svg>
      Continue with Google <span class="coming-soon">SOON</span>
    </button>
    <div class="auth-divider"><span>OR SIGN UP WITH EMAIL</span></div>

    <form method="post">
      {% csrf_token %}
      <div class="auth-field">
        <label class="auth-label" for="id_email">Email</label>
        <input class="text-input" type="email" name="email" id="id_email" autocomplete="email" placeholder="you@example.com" value="{{ form.email.value|default:'' }}" required>
        {% if form.email.errors %}<div class="auth-error">{{ form.email.errors|striptags }}</div>{% endif %}
      </div>
      <div class="auth-field">
        <label class="auth-label" for="id_password">Password</label>
        <input class="text-input" type="password" name="password" id="id_password" autocomplete="new-password" placeholder="Create a password" required>
        {% if form.password.errors %}<div class="auth-error">{{ form.password.errors|striptags }}</div>{% else %}<div class="auth-error" style="color:var(--muted);">At least 8 characters.</div>{% endif %}
      </div>
      <button class="btn btn--primary btn--block" type="submit">Create account</button>
      <p style="margin:12px 0 0; font-size:11.5px; line-height:1.5; color:var(--muted); text-align:center;">By creating an account you agree to our Terms and Privacy Policy.</p>
    </form>
    <p class="auth-foot">Already have an account? <a href="{% url 'login' %}">Sign in</a></p>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `../../.venv-web/bin/pytest accounts/tests/test_account_flow.py accounts/tests/test_auth.py -q`
Expected: PASS — new smoke test plus existing signup POST tests (`test_signup_creates_user_and_logs_in`, `test_email_must_be_unique`, `test_signup_does_not_require_display_name`).

- [ ] **Step 5: Commit**

```bash
git add apps/web/templates/accounts/signup.html apps/web/accounts/tests/test_account_flow.py
git commit -m "feat(accounts): restyle create account to Mise split-panel

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Full verification + open PR

**Files:** none (verification + PR)

- [ ] **Step 1: Run the full accounts suite**

Run (from `apps/web/`): `../../.venv-web/bin/pytest accounts/ -q`
Expected: PASS — all prior tests plus the new account-flow and password-reset tests (no regressions).

- [ ] **Step 2: Run the whole web test suite**

Run (from `apps/web/`): `../../.venv-web/bin/pytest -q`
Expected: PASS (no regressions elsewhere).

- [ ] **Step 3: Manual smoke via the running-web-app skill**

Use the `running-web-app` project skill (under `apps/web/.claude/skills`) to launch the app and visually confirm: `/login/`, `/signup/`, `/password-reset/`, `/password-reset/done/`, `/verify-email/` render the Mise design; the Google button is disabled; submitting a reset request prints the email (with the `/reset/<uid>/<token>/` link) to the runserver console.

- [ ] **Step 4: Push and open the PR into main**

```bash
git push -u origin feat/mise-account-flow
gh pr create --base main --title "feat(accounts): Mise account flow — sign in, sign up, password reset, verify-email" --body "$(cat <<'EOF'
Implements `mise/Account Flow.dc.html` (Claude Design import).

## What
- Restyle **Sign in** and **Create account** to the Mise split-panel design.
- Real **password reset** (forgot → email → set new → done) via Django's built-in auth views + Mise-styled templates. Console email backend by default in dev (no secrets); override via `DJANGO_EMAIL_BACKEND`.
- Standalone **Verify email** preview screen at `/verify-email/`.
- Drop `display_name` from the signup form (stays on the model + profile).

## Placeholders (per spec, non-functional by design)
- "Continue with Google" is rendered but disabled with a "Coming soon" affordance.
- Email-code verification is a styled preview, not wired into signup.

## Tests
- Password-reset cycle (email link → set new password → login).
- Smoke GETs for login / signup / verify-email / reset screens.
- Existing auth + onboarding tests still pass.

Spec: `docs/superpowers/specs/2026-06-28-account-flow-design.md`
Plan: `docs/superpowers/plans/2026-06-28-account-flow.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review notes

- **Spec coverage:** import source (T1) ✓; restyle sign-in (T5) / create-account (T6) ✓; drop display_name (T2) ✓; password reset incl. settings + env (T4) ✓; verify-email preview (T3) ✓; CSS additions split across T3 (single-card) + T5 (split-panel) ✓; Google disabled placeholder (T5/T6) ✓; tests (T2/T3/T4/T5/T6) ✓.
- **Ordering / no NoReverseMatch:** reset routes (T4) precede the login template's `{% url 'password_reset' %}` (T5); `base_auth.html` (T3) precedes all consumers; `signup` form change (T2) precedes the signup template (T6).
- **Type/name consistency:** URL names (`password_reset`, `password_reset_done`, `password_reset_confirm`, `password_reset_complete`, `verify_email`) used consistently across urls, templates, and tests. Form field names match Django's `AuthenticationForm` (`username`/`password`), `PasswordResetForm` (`email`), and `SetPasswordForm` (`new_password1`/`new_password2`).
</content>
