# Account & Onboarding Flow — Design

**Date:** 2026-06-28
**Status:** Approved (design), pending implementation plan
**Design source:** `mise/Account Flow.dc.html` (+ companion `mise/Account Creation.dc.html`)
from the Claude Design project "Onboarding account creation basics".

## Summary

Build out the email/password account flow to the Mise design system: restyle the
existing **Sign in** and **Create account** screens to the polished split-panel
layout, wire **password reset** for real using Django's built-in views with
Mise-styled templates, and add a standalone **Verify email** preview screen.
The flow hands off to the already-built taste-preferences onboarding wizard.

The current `login.html` / `signup.html` are unstyled stubs (`{{ form.as_p }}`);
this PR makes them match the design and adds the two new screens the wireframe
introduces (verify email, password reset).

## Goals

- Restyle Sign in + Create account to the Mise split-panel design (brand panel +
  form panel), keeping the existing email/password auth behavior.
- Real, working password reset (forgot → email → set new password → done) using
  Django's built-in auth views and Mise-styled templates.
- A standalone Verify-email preview screen styled per the design.
- Reuse the existing token/component CSS system; add a small, focused set of
  `.auth-*` classes rather than per-template inline styles.

## Non-Goals (placeholders / YAGNI)

- **Real Google OAuth.** "Continue with Google" is rendered per the design but
  **disabled** with a subtle "Coming soon" label. No `django-allauth`, no secrets.
- **Real email-code verification.** The Verify-email screen is a styled preview at
  its own URL; it is **not** inserted into the signup flow (signup still goes
  straight to onboarding). Code boxes are display-only; buttons are inert.
- No changes to the onboarding wizard or the discover/feed destination.

## User flow (from the wireframe)

```
Sign in ──(returning user)──────────────────────────────────► Your feed (discover, exists)
  │  └─ Forgot password? ─► Reset password ─► Check inbox ─(email link)─► Set new password ─► Done ─► Sign in
  └─ Create an account ─► Create account ─► (onboarding taste wizard, exists) ─► Your feed

Verify email .......... standalone styled preview (not wired into the live flow)
```

## Components

### Templates
- `base_auth.html` — minimal shell: tokens/fonts, full-height `--paper` background,
  centered content, flash messages, **no app-bar**. The design auth screens are
  full-bleed with no top nav.
- `accounts/_auth_shell.html` — partial rendering the split-panel card (brand panel
  + form panel). Brand copy passed in via context/block so login and signup can
  differ ("WELCOME BACK" vs "JOIN MISE", perks, headings).
- `accounts/login.html` — Sign in, hand-rendered `AuthenticationForm`
  (`form.username` = email, `form.password`), Google (disabled), "Forgot password?"
  link → `password_reset`, footer link → `signup`, inline auth errors.
- `accounts/signup.html` — Create account, hand-rendered `SignupForm`
  (email + password, ≥8 hint), Google (disabled), legal copy, footer link → `login`,
  inline field errors.
- `accounts/verify_email.html` — styled 6-digit-code preview screen (inert).
- Password-reset templates (Mise-styled):
  - `accounts/password_reset_form.html` — "Reset your password" / Send reset link
  - `accounts/password_reset_done.html` — "Check your inbox" (envelope screen)
  - `accounts/password_reset_confirm.html` — set a new password (not in wireframe,
    required by the flow; styled consistently)
  - `accounts/password_reset_complete.html` — "Password updated" → Back to sign in
  - `accounts/password_reset_email.txt` — plain-text email body with reset link
  - `accounts/password_reset_subject.txt` — email subject line

### Views / URLs (`accounts/`)
- `AppLoginView` — unchanged behavior; template restyled.
- `signup` — unchanged behavior; template restyled.
- `verify_email` — new trivial view rendering `accounts/verify_email.html` (GET).
- Password reset — wire the four `django.contrib.auth.views` classes in
  `accounts/urls.py`, each pointing at the Mise template above, with
  `success_url`s chaining through the flow:
  - `password-reset/` → `PasswordResetView` (name `password_reset`)
  - `password-reset/done/` → `PasswordResetDoneView` (name `password_reset_done`)
  - `reset/<uidb64>/<token>/` → `PasswordResetConfirmView` (name `password_reset_confirm`)
  - `reset/done/` → `PasswordResetCompleteView` (name `password_reset_complete`)

### Forms
- `SignupForm.Meta.fields` changes from `["email", "display_name"]` to `["email"]`.
  The design's create-account screen shows only email + password. `display_name`
  stays on the model and remains editable on the profile page. Existing auth tests
  post `display_name` but don't assert it, so they continue to pass.

### CSS (`static/css/components.css`)
Add a focused set of classes (reusing existing `.btn`, `.text-input`, tokens):
- `.auth-shell` — centered split-panel card (grid: brand | form), responsive
  (panels stack below a breakpoint).
- `.auth-brand` — accent-filled brand panel (logo, tagline, perks list).
- `.auth-form` — form panel padding/layout.
- `.auth-label` — mono uppercase field label.
- `.auth-divider` — "OR" rule.
- `.btn--social` — outlined social button; disabled state carries the
  "Coming soon" affordance.
- `.code-input` — the 6-box verification code row.

### Settings (`config/settings.py`)
Add, with env overrides:
- `EMAIL_BACKEND` defaulting to `django.core.mail.backends.console.EmailBackend`.
  Dev prints the reset email (with link) to the runserver console — works with no
  secrets and never silently fails to an unconfigured SMTP server. Production
  overrides via `DJANGO_EMAIL_BACKEND`.
- `DEFAULT_FROM_EMAIL` defaulting to a `Mise <no-reply@mise.local>`-style value,
  override via `DJANGO_DEFAULT_FROM_EMAIL`.

## Design source import

Save the two design docs under `design/mise/` as read-only reference (mirrors the
existing `docs(design): import Mise design system source` commit pattern):
`design/mise/Account Flow.dc.html`, `design/mise/Account Creation.dc.html`.

## Error handling

- Login: invalid credentials → Django's standard non-field error, rendered inline
  in the form panel in Mise styling.
- Signup: duplicate email / short password → field errors rendered inline (re-render
  with 200, matching existing `test_email_must_be_unique`).
- Password reset: unknown email behaves like Django default (no account enumeration —
  always shows "check your inbox"). Expired/invalid token → confirm view shows the
  standard invalid-link state, styled.

## Testing

- **Password reset (real):** POST a known email to `password_reset` → 302 to
  `password_reset_done`; assert one message in `django.core.mail.outbox` containing
  a reset link; follow the link to `password_reset_confirm`, POST a new password,
  assert the user's password is updated and login works with it.
- **Signup:** still creates the user and logs them in after dropping `display_name`
  from the form.
- **Smoke GETs:** restyled `login`, `signup`, `verify_email`, and the reset-form /
  reset-done pages return 200 with their key copy.

## Open risks

- Password-reset emails require an email backend; the console default keeps dev
  working without secrets but means prod must set `DJANGO_EMAIL_BACKEND` +
  credentials before reset works there. Called out in `.env.example`.
</content>
</invoke>
