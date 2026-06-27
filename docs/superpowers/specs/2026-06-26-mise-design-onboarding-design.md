# Mise component library + onboarding wizard

**Date:** 2026-06-26
**Status:** Approved — ready for implementation plan

## Summary

Bring the **Mise** design system into the Django web app (`apps/web`) as a reusable
CSS component library, and build a new **taste-preferences onboarding wizard** that
runs after signup.

The app today is bare Django (htmx + Alpine, no CSS, no static files). The Mise
design system (`design/Mise Design System.dc.html`) defines tokens (4 palettes,
light/dark), typography, and components (buttons, chips, badges, inputs, and the
signature video→recipe primitives). This work ports that system into real,
maintainable CSS and uses it for the onboarding flow.

## Scope

**In scope**
- Static-files setup + `mise.css` design tokens and full component class library.
- Restyle the global shell (`base.html`) and the recipe-card partial.
- Onboarding wizard: model fields + migration, views, URLs, templates, tests.

**Out of scope (follow-up PRs)**
- Full per-screen rebuilds of discover hero, recipe detail, saved, favorites.
  These inherit the shell + fonts from this PR but are not rebuilt here.
- Palette / dark-mode switcher UI (tokens are wired; no toggle this PR).
- Recommendation logic that turns stored prefs into a ranked "For you" feed.

## 1. CSS foundation — `apps/web/static/css/mise.css`

- Configure Django static files: `STATIC_URL`, `STATICFILES_DIRS` pointing at
  `apps/web/static/`, and `{% load static %}` in `base.html`.
- Port design tokens as CSS custom properties on `:root`:
  - neutrals (`--paper`, `--surface`, `--surface-2`, `--ink`, `--ink-2`,
    `--muted`, `--line`, `--line-2`), shadows (`--shadow-1`, `--shadow-2`),
    accents (`--accent`, `--accent-press`, `--secondary`, `--on-accent`, and the
    derived `--accent-soft`/`--accent-softer` via `color-mix`).
  - radius scale, spacing on a base-4 grid, type scale.
- Default palette **Ember / light** (the `.dc` default). The other three palettes
  and dark-mode neutrals are included as `[data-theme="…"]` and
  `@media (prefers-color-scheme: dark)` blocks so a switcher is trivial later —
  **no switcher UI in this PR**.
- Fonts via Google Fonts `<link>` in `base.html`: **Newsreader** (display/serif),
  **Hanken Grotesk** (UI body), **Spline Sans Mono** (meta/labels).
- Keyframes ported: `mise-shimmer`, `mise-spin`, `mise-pulse`.

## 2. Component class library

Port every component from the design system's `Components` section as CSS classes,
replacing the source's inline styles. Class names follow a flat, BEM-ish convention.

- **Buttons & actions:** `.btn` base + `.btn--primary`, `.btn--secondary`,
  `.btn--ghost`, `:disabled`, `.btn--icon` (round 44px), pill radius.
- **Chips, tags & badges:** `.chip` + `.chip--selected` (selectable filter chip);
  `.badge` + variants `--ai` (AI extracted), `--source` (provenance, e.g. YouTube),
  `--difficulty`, `--time`.
- **Inputs & search:** `.search-field` (pill with leading icon + ⏎ hint),
  `.text-input`, `.select-field` (with chevron), `.toggle` (track + knob).
- **Signature video→recipe primitives:**
  - `.video-card` — thumbnail (aspect 16/10) + meta + title + time/difficulty
    badges + save toggle.
  - `.ingredient-row` — checkbox, amount (mono), name; checked state strikes through.
  - `.step` — numbered circle + text + "jump to timestamp" button.
  - `.extraction-state` — icon + label + shimmer progress bar.

## 3. Where components are used (so they are real, not just a stylesheet)

- `base.html`: Mise wordmark top bar, search field, nav links, flash messages,
  body font + background from tokens.
- `recipes/_recipe_card.html`: restyle to the Mise `.video-card` (already included
  by the discovery feed, so the component renders in a real screen).
- Onboarding templates consume `.btn`, `.chip`, progress, and the layout shell.

## 4. Onboarding wizard — taste preferences

### Data model (`accounts.User`)
Add fields:
- `preferred_cuisines` — `JSONField(default=list)` — list of cuisine strings.
- `dietary_tags` — `JSONField(default=list)` — list of diet strings.
- `max_cook_time_minutes` — `PositiveIntegerField(null=True, blank=True)`.
- `onboarding_completed` — `BooleanField(default=False)`.

One migration in `accounts/migrations/`. `JSONField(default=list)` uses the
callable default (not a shared mutable). Cuisine/diet option lists live as a
constant in the accounts app so templates and validation share one source.

### Flow
Three steps, server-rendered, each posting forward to the next:
1. **Welcome** — brand hero (Newsreader headline, Mise voice), "Get started" CTA,
   "Skip for now" link.
2. **Cuisines + diet** — selectable `.chip` grids. Alpine tracks selection state
   client-side; selected values submit as form fields. Progress: step 2 of 3.
3. **Max cook time + finish** — cook-time options (chips or select), "Finish" CTA.
   On submit, save all prefs, set `onboarding_completed = True`, redirect to
   `discover`.

A visible progress indicator (`Step N of 3` with filled/empty dots) appears on
steps 2–3.

### Gating
- After signup (`accounts.views.signup`), redirect to `onboarding` instead of
  `discover`.
- Authenticated users with `onboarding_completed = False` are redirected into the
  wizard when they hit the app. Implemented as a small reusable check (decorator or
  helper used by the relevant views) rather than global middleware, to keep the
  blast radius small and testable.
- **Skip** marks `onboarding_completed = True` with empty prefs and lands on
  `discover`.

### URLs / views
New routes in `accounts/urls.py` and views in `accounts/views.py` (e.g.
`onboarding_welcome`, `onboarding_tastes`, `onboarding_finish`, plus `skip`).
Step state is carried in the POSTed form, not the session, to keep it simple.

## 5. Testing

Match the existing pytest setup (`apps/web/pytest.ini`, `conftest.py`,
per-app `tests/` packages). Cover:
- Model: new fields default correctly (`preferred_cuisines == []`,
  `onboarding_completed is False`).
- Signup redirects a new user to onboarding (not discover).
- Gating: an authenticated user with `onboarding_completed = False` is redirected
  into the wizard; a completed user is not.
- Completing the wizard saves the chosen cuisines/diet/cook-time, sets
  `onboarding_completed = True`, and redirects to discover.
- Skip sets `onboarding_completed = True` with empty prefs and redirects to discover.

No CSS/visual regression tests (out of scope); component correctness is verified by
the templates rendering without error in the above view tests.

## Open questions

None. Scope boundary (component library + shell + recipe card + onboarding; full
per-screen rebuilds deferred) confirmed with the user.
