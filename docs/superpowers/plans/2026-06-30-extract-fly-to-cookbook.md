# Extract fly-to-cookbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clicking an Extract button on Discover search results flies a clone of the card into the Saved (cookbook) nav tab, pops the tab's count badge, settles the button into an "In cookbook" check state, and shows the recipe in the cookbook as an in-progress card until extraction finishes.

**Architecture:** Optimistic front-end flourish (Web Animations API in a static JS module) layered on the existing HTMX extract flow. The real Celery job still fires; the extract response now returns an "In cookbook" partial instead of a poller+redirect. The cookbook (`saved`) view surfaces active `ExtractionJob`s as placeholder cards that poll a new endpoint and self-replace with the finished recipe. A context processor feeds the live cookbook count to the global nav badge.

**Tech Stack:** Django templates + HTMX 1.9 + Alpine 3 (existing), vanilla JS (Web Animations API), pytest / pytest-django (`.venv-web/bin/pytest`).

## Global Constraints

- Run tests from repo root with `.venv-web/bin/pytest apps/web/recipes/tests/...` (Django app lives at `apps/web`, settings `config.settings`, conftest already configures it).
- Cookbook = `Recipe.objects.filter(owner=user)`; nav label is "Saved", url name `saved`, route `/saved/`.
- "Active" / in-progress job = `ExtractionJob.objects.filter(owner=user).exclude(status__in=[ExtractionJob.Status.DONE, ExtractionJob.Status.FAILED])`. Use this exact predicate everywhere a count or list of in-progress jobs is needed.
- Only the search Extract button posts to url name `extract_recipe` (`/youtube/extract/`); do NOT touch the ingest `start_job` / `_job_status` flow.
- Reuse existing CSS tokens (`--accent`, `--accent-soft`, `--accent-line`, `--on-soft`, `--on-accent`, `--r-pill`, `--surface-2`, `--secondary`, `--ink-2`) and the existing `.rcard` / `.lrow` / `.rthumb` / `.ceyebrow` / `.rtitle` cookbook shells. No new color values.
- Commit after each task. Conventional Commit subject, and end every commit body with:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## File Structure

- `apps/web/recipes/context_processors.py` *(new)* — `cookbook_badge(request)` → `{"cookbook_count": int}` for authed users.
- `apps/web/config/settings.py` *(modify)* — register the context processor.
- `apps/web/templates/base.html` *(modify)* — Saved-tab badge markup + `{% block scripts %}`.
- `apps/web/templates/recipes/_extract_done.html` *(new)* — "In cookbook" check-state partial.
- `apps/web/templates/recipes/_cookbook_pending_card.html` *(new)*, `_cookbook_pending_row.html` *(new)* — in-progress placeholders (grid/list) with self-poll.
- `apps/web/templates/recipes/_cookbook.html` *(modify)* — render `pending_jobs` above results.
- `apps/web/templates/recipes/discover.html` *(modify)* — load the fly script.
- `apps/web/static/js/extract-fly.js` *(new)* — the fly animation + badge pop.
- `apps/web/static/css/components.css` *(modify)* — `.nav-badge`, `.extract--done`, `.rcard--pending`/`.lrow--pending`, `.pending-spin`, `@keyframes spin`.
- `apps/web/recipes/views.py` *(modify)* — `extract_from_captions` response; `saved` `pending_jobs`+`total`; new `cookbook_job_card`.
- `apps/web/recipes/urls.py` *(modify)* — `cookbook_job_card` route.
- Tests: `tests/test_context_processors.py` *(new)*, `tests/test_extract.py` *(modify)*, `tests/test_pending_cookbook.py` *(new)*, `tests/test_landing.py` or `test_discover.py` *(modify, smoke)*.

---

## Task 1: Saved-tab cookbook count badge

**Files:**
- Create: `apps/web/recipes/context_processors.py`
- Create: `apps/web/recipes/tests/test_context_processors.py`
- Modify: `apps/web/config/settings.py:57-61` (context_processors list)
- Modify: `apps/web/templates/base.html:22` (Saved link)
- Modify: `apps/web/static/css/components.css` (append `.nav-badge`)

**Interfaces:**
- Produces: `recipes.context_processors.cookbook_badge(request) -> dict`. Returns `{}` for anonymous; `{"cookbook_count": <recipes + active jobs>}` for authed. Template var `cookbook_count`. Nav badge span carries `id`-less `data-cookbook-badge` attr inside `<a id="saved-tab">` (consumed by Task 4).

- [ ] **Step 1: Write the failing test**

Create `apps/web/recipes/tests/test_context_processors.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from recipes.context_processors import cookbook_badge
from recipes.models import ExtractionJob, Recipe

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="u@e.com", password="supersecret", onboarding_completed=True
    )


def test_badge_counts_recipes_plus_active_jobs(rf, user):
    Recipe.objects.create(owner=user, title="A")
    Recipe.objects.create(owner=user, title="B")
    ExtractionJob.objects.create(
        owner=user, source="youtube_captions",
        status=ExtractionJob.Status.EXTRACTING,
    )
    # DONE and FAILED jobs must NOT be counted.
    ExtractionJob.objects.create(
        owner=user, source="youtube_captions", status=ExtractionJob.Status.DONE
    )
    ExtractionJob.objects.create(
        owner=user, source="youtube_captions", status=ExtractionJob.Status.FAILED
    )
    req = rf.get("/")
    req.user = user
    assert cookbook_badge(req) == {"cookbook_count": 3}


def test_badge_empty_for_anonymous(rf):
    req = rf.get("/")
    req.user = AnonymousUser()
    assert cookbook_badge(req) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-web/bin/pytest apps/web/recipes/tests/test_context_processors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'recipes.context_processors'`.

- [ ] **Step 3: Create the context processor**

Create `apps/web/recipes/context_processors.py`:

```python
from .models import ExtractionJob, Recipe


def cookbook_badge(request):
    """Live cookbook size for the Saved nav badge: saved recipes plus
    in-progress extractions (each renders as a pending cookbook card)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    recipes = Recipe.objects.filter(owner=user).count()
    active = (
        ExtractionJob.objects.filter(owner=user)
        .exclude(status__in=[ExtractionJob.Status.DONE, ExtractionJob.Status.FAILED])
        .count()
    )
    return {"cookbook_count": recipes + active}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv-web/bin/pytest apps/web/recipes/tests/test_context_processors.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Register the context processor**

In `apps/web/config/settings.py`, add the line to the `context_processors` list (after the messages processor):

```python
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "recipes.context_processors.cookbook_badge",
            ],
```

- [ ] **Step 6: Render the badge in the nav**

In `apps/web/templates/base.html`, replace the Saved link (line 22):

```html
        <a id="saved-tab" href="{% url 'saved' %}">Saved<span class="nav-badge{% if not cookbook_count %} nav-badge--empty{% endif %}" data-cookbook-badge>{{ cookbook_count|default:0 }}</span></a>
```

(The badge is always rendered for authed users so the optimistic +1 in Task 4 has a node to reveal; `nav-badge--empty` hides it at 0.)

- [ ] **Step 7: Add badge CSS**

Append to `apps/web/static/css/components.css`:

```css
/* Saved-tab cookbook count badge */
.nav-badge { display: inline-block; margin-left: 7px; padding: 3px 6px; border-radius: var(--r-pill); background: var(--accent-soft); color: var(--on-soft); border: 1px solid var(--accent-line); font-family: var(--font-mono); font-size: 10px; font-weight: 600; line-height: 1; letter-spacing: .02em; vertical-align: middle; }
.nav-badge--empty { display: none; }
```

- [ ] **Step 8: Smoke-check the rendered page**

Run: `.venv-web/bin/pytest apps/web/recipes/tests/ -q`
Expected: PASS (no regressions). Then verify the nav renders the badge for an authed user (any authed page test still green).

- [ ] **Step 9: Commit**

```bash
git add apps/web/recipes/context_processors.py apps/web/recipes/tests/test_context_processors.py apps/web/config/settings.py apps/web/templates/base.html apps/web/static/css/components.css
git commit -m "feat(recipes): live cookbook count badge on Saved nav tab"
```

---

## Task 2: Extract returns "In cookbook" state (no poller/redirect)

**Files:**
- Create: `apps/web/templates/recipes/_extract_done.html`
- Modify: `apps/web/recipes/views.py:153` (`extract_from_captions` return)
- Modify: `apps/web/static/css/components.css` (append `.extract--done`)
- Modify: `apps/web/recipes/tests/test_extract.py` (add assertion)

**Interfaces:**
- Consumes: existing `extract_from_captions` already creates the job + calls `run_extraction_job.delay`.
- Produces: POST to `/youtube/extract/` with captions returns `recipes/_extract_done.html` (HTTP 200) containing the text `In cookbook` and a `.extract--done` span; no `hx-get` poller, no `HX-Redirect`.

- [ ] **Step 1: Update the test (failing)**

In `apps/web/recipes/tests/test_extract.py`, add:

```python
def test_extract_returns_in_cookbook_state(auth_client):
    with patch("recipes.views.youtube.fetch_transcript", return_value="boil pasta"), \
         patch("recipes.views.run_extraction_job.delay"):
        resp = auth_client.post(
            "/youtube/extract/", {"video_id": "abc", "title": "Pasta"}
        )
    assert resp.status_code == 200
    assert b"In cookbook" in resp.content
    assert b"extract--done" in resp.content
    assert b"hx-get" not in resp.content          # no status poller
    assert "HX-Redirect" not in resp                # stays on the results page
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-web/bin/pytest apps/web/recipes/tests/test_extract.py::test_extract_returns_in_cookbook_state -v`
Expected: FAIL — response still renders `_job_status.html` ("In cookbook" not present).

- [ ] **Step 3: Create the partial**

Create `apps/web/templates/recipes/_extract_done.html`:

```html
<span class="extract extract--done" aria-live="polite">
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg>In cookbook{% if layout == "list" %} recipe{% endif %}
</span>
```

- [ ] **Step 4: Return the partial from the view**

In `apps/web/recipes/views.py`, change the final line of `extract_from_captions` (currently `return render(request, "recipes/_job_status.html", {"job": job})`) to:

```python
    run_extraction_job.delay(job.id, transcript=transcript)
    return render(request, "recipes/_extract_done.html", {"job": job})
```

- [ ] **Step 5: Add the "In cookbook" CSS state**

Append to `apps/web/static/css/components.css`:

```css
/* Settled state after Extract: recipe is (optimistically) in the cookbook */
.extract--done { background: var(--accent-soft); color: var(--on-soft); box-shadow: none; cursor: default; }
.extract--done:hover { background: var(--accent-soft); }
```

- [ ] **Step 6: Run the extract tests**

Run: `.venv-web/bin/pytest apps/web/recipes/tests/test_extract.py -v`
Expected: PASS (all, including the existing `test_extract_with_captions_creates_job` which still finds the job + delay).

- [ ] **Step 7: Commit**

```bash
git add apps/web/templates/recipes/_extract_done.html apps/web/recipes/views.py apps/web/static/css/components.css apps/web/recipes/tests/test_extract.py
git commit -m "feat(recipes): Extract settles to 'In cookbook' instead of poller+redirect"
```

---

## Task 3: In-progress recipe cards in the cookbook

**Files:**
- Modify: `apps/web/recipes/views.py` (`saved` — add `pending_jobs` + `total`; new `cookbook_job_card`)
- Modify: `apps/web/recipes/urls.py` (route)
- Create: `apps/web/templates/recipes/_cookbook_pending_card.html`
- Create: `apps/web/templates/recipes/_cookbook_pending_row.html`
- Modify: `apps/web/templates/recipes/_cookbook.html` (render `pending_jobs`)
- Modify: `apps/web/static/css/components.css` (pending styles + `@keyframes spin`)
- Create: `apps/web/recipes/tests/test_pending_cookbook.py`

**Interfaces:**
- Consumes: `_annotated(qs, user)` (adds `is_favorite`); existing `_cookbook_card.html` / `_cookbook_row.html` (need `recipe` + `view`).
- Produces:
  - `saved` context gains `pending_jobs: list[ExtractionJob]` (empty when `has_filters`); `total` includes `len(pending_jobs)` when unfiltered.
  - `cookbook_job_card(request, pk)` at url name `cookbook_job_card`, route `/jobs/<int:pk>/card/`. Reads `?view=grid|list`. DONE+recipe → real cookbook card/row; FAILED → failed placeholder (no poll); else → pending placeholder (polls). 404 for another user's job.
  - Pending placeholder root: `<div ... id="job-{{ job.id }}">` with `hx-get` self-poll unless `failed`.

- [ ] **Step 1: Write the failing tests**

Create `apps/web/recipes/tests/test_pending_cookbook.py`:

```python
import pytest
from django.contrib.auth import get_user_model

from recipes.models import ExtractionJob, Recipe

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="u@e.com", password="supersecret", onboarding_completed=True
    )


@pytest.fixture
def auth_client(client, user):
    client.login(username="u@e.com", password="supersecret")
    return client


def _job(user, **kw):
    kw.setdefault("source", "youtube_captions")
    kw.setdefault("status", ExtractionJob.Status.EXTRACTING)
    kw.setdefault("title", "Cacio e Pepe")
    return ExtractionJob.objects.create(owner=user, **kw)


def test_saved_shows_pending_card_unfiltered(auth_client, user):
    _job(user)
    resp = auth_client.get("/saved/")
    assert resp.status_code == 200
    assert b"EXTRACTING" in resp.content
    assert b"Cacio e Pepe" in resp.content
    # total reflects the pending card (0 recipes + 1 pending)
    assert b"1 RECIPE" in resp.content


def test_saved_hides_pending_when_filtered(auth_client, user):
    _job(user)
    resp = auth_client.get("/saved/?q=anything")
    assert resp.status_code == 200
    assert b"EXTRACTING" not in resp.content


def test_job_card_running_returns_pending(auth_client, user):
    job = _job(user)
    resp = auth_client.get(f"/jobs/{job.id}/card/")
    assert resp.status_code == 200
    assert b"EXTRACTING" in resp.content
    assert b"hx-get" in resp.content          # keeps polling


def test_job_card_done_returns_recipe_card(auth_client, user):
    recipe = Recipe.objects.create(owner=user, title="Done Pasta")
    job = _job(user, status=ExtractionJob.Status.DONE, recipe=recipe)
    resp = auth_client.get(f"/jobs/{job.id}/card/")
    assert resp.status_code == 200
    assert b"Done Pasta" in resp.content
    assert b"EXTRACTING" not in resp.content
    assert b"hx-get" not in resp.content       # stops polling


def test_job_card_failed_stops_polling(auth_client, user):
    job = _job(user, status=ExtractionJob.Status.FAILED, error="bad transcript")
    resp = auth_client.get(f"/jobs/{job.id}/card/")
    assert resp.status_code == 200
    assert b"FAILED" in resp.content
    assert b"hx-get" not in resp.content


def test_job_card_other_user_404(auth_client, db):
    other = User.objects.create_user(email="o@e.com", password="supersecret")
    job = _job(other)
    resp = auth_client.get(f"/jobs/{job.id}/card/")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv-web/bin/pytest apps/web/recipes/tests/test_pending_cookbook.py -v`
Expected: FAIL — `/jobs/<id>/card/` 404 (no route) and `/saved/` lacks pending markup.

- [ ] **Step 3: Add `pending_jobs` + `total` to the `saved` view**

In `apps/web/recipes/views.py`, inside `saved`, hoist `has_filters` and build `pending_jobs`. Replace the `has_filters` computation: locate `total = len(cookbook)` (just after `cookbook = list(...)`) and add directly below it:

```python
    cookbook = list(_annotated(Recipe.objects.filter(owner=user), user))
    total = len(cookbook)
```

Then, immediately before the `return render(...)` block, add:

```python
    has_filters = bool(q or fav or any(sel.values()))
    pending_jobs = []
    if not has_filters:
        pending_jobs = list(
            ExtractionJob.objects.filter(owner=user).exclude(
                status__in=[ExtractionJob.Status.DONE, ExtractionJob.Status.FAILED]
            )
        )
        total += len(pending_jobs)
```

In the render context dict, set `"total": total`, replace `"has_filters": bool(q or fav or any(sel.values()))` with `"has_filters": has_filters`, and add `"pending_jobs": pending_jobs,`.

- [ ] **Step 4: Add the `cookbook_job_card` view**

Append to `apps/web/recipes/views.py` (near the `saved` view):

```python
@login_required
@onboarding_required
def cookbook_job_card(request, pk):
    job = get_object_or_404(ExtractionJob, pk=pk, owner=request.user)
    view = "list" if request.GET.get("view") == "list" else "grid"
    if job.status == ExtractionJob.Status.DONE and job.recipe_id:
        recipe = _annotated(
            Recipe.objects.filter(pk=job.recipe_id), request.user
        ).first()
        template = (
            "recipes/_cookbook_row.html" if view == "list"
            else "recipes/_cookbook_card.html"
        )
        return render(request, template, {"recipe": recipe, "view": view})
    template = (
        "recipes/_cookbook_pending_row.html" if view == "list"
        else "recipes/_cookbook_pending_card.html"
    )
    failed = job.status == ExtractionJob.Status.FAILED
    return render(request, template, {"job": job, "view": view, "failed": failed})
```

- [ ] **Step 5: Add the route**

In `apps/web/recipes/urls.py`, add inside `urlpatterns` (after the `job_status` line):

```python
    path("jobs/<int:pk>/card/", views.cookbook_job_card, name="cookbook_job_card"),
```

- [ ] **Step 6: Create the pending grid card**

Create `apps/web/templates/recipes/_cookbook_pending_card.html`:

```html
<div class="rcard rcard--pending" id="job-{{ job.id }}"{% if not failed %} hx-get="{% url 'cookbook_job_card' job.id %}?view=grid" hx-trigger="load delay:1800ms" hx-swap="outerHTML"{% endif %}>
  <div class="rthumb" style="background:linear-gradient(150deg, var(--surface-2), color-mix(in srgb, var(--secondary) 18%, var(--surface-2)));">
    {% if failed %}<span class="play"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"></path></svg></span>{% else %}<span class="pending-spin" role="status" aria-label="Extracting recipe"></span>{% endif %}
  </div>
  <div style="padding:15px 16px 17px;">
    <div class="ceyebrow">{% if failed %}EXTRACTION FAILED{% else %}EXTRACTING…{% endif %}</div>
    <h4 class="rtitle">{{ job.title|default:"Untitled recipe" }}</h4>
    {% if failed %}<div class="credit"><span class="cn" style="color:var(--ink-2);">{{ job.error|default:"Something went wrong" }}</span></div>{% endif %}
  </div>
</div>
```

- [ ] **Step 7: Create the pending list row**

Create `apps/web/templates/recipes/_cookbook_pending_row.html`:

```html
<div class="lrow lrow--pending" id="job-{{ job.id }}"{% if not failed %} hx-get="{% url 'cookbook_job_card' job.id %}?view=list" hx-trigger="load delay:1800ms" hx-swap="outerHTML"{% endif %}>
  <div class="lthumb" style="background:linear-gradient(150deg, var(--surface-2), color-mix(in srgb, var(--secondary) 18%, var(--surface-2)));">
    {% if failed %}<span class="play"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"></path></svg></span>{% else %}<span class="pending-spin" role="status" aria-label="Extracting recipe"></span>{% endif %}
  </div>
  <div style="flex:1; display:flex; flex-direction:column;">
    <div class="ceyebrow">{% if failed %}EXTRACTION FAILED{% else %}EXTRACTING…{% endif %}</div>
    <h4 class="ltitle">{{ job.title|default:"Untitled recipe" }}</h4>
    {% if failed %}<div class="credit"><span class="cn" style="color:var(--ink-2);">{{ job.error|default:"Something went wrong" }}</span></div>{% endif %}
  </div>
</div>
```

- [ ] **Step 8: Render `pending_jobs` in the cookbook**

In `apps/web/templates/recipes/_cookbook.html`, inside the `{% if recipes %}` branch, the placeholders must appear even when there are no saved recipes yet. Replace the results block (the `{% if recipes %} ... {% else %} ... {% endif %}` that renders grid/list, lines ~61-85) so pending cards render first. Change the opening of that block to:

```html
{% if recipes or pending_jobs %}
  {% if view == 'list' %}
  <div>
    {% for job in pending_jobs %}{% include "recipes/_cookbook_pending_row.html" %}{% endfor %}
    {% for recipe in recipes %}{% include "recipes/_cookbook_row.html" %}{% endfor %}
  </div>
  {% else %}
  <div class="grid3">
    {% for job in pending_jobs %}{% include "recipes/_cookbook_pending_card.html" %}{% endfor %}
    {% for recipe in recipes %}{% include "recipes/_cookbook_card.html" %}{% endfor %}
  </div>
  {% endif %}
{% elif has_filters %}
```

(The `{% elif has_filters %}` and final `{% else %}` empty states stay unchanged.)

- [ ] **Step 9: Add pending CSS + spin keyframe**

Append to `apps/web/static/css/components.css`:

```css
/* In-progress extraction placeholders in the cookbook */
@keyframes spin { to { transform: rotate(360deg); } }
.rcard--pending, .lrow--pending { animation: pending-pulse 1.6s ease-in-out infinite; }
@keyframes pending-pulse { 0%, 100% { opacity: 1; } 50% { opacity: .72; } }
.pending-spin { width: 26px; height: 26px; border: 3px solid color-mix(in srgb, var(--accent) 28%, transparent); border-right-color: var(--accent); border-radius: 50%; display: inline-block; animation: spin .7s linear infinite; }
```

- [ ] **Step 10: Run the pending tests**

Run: `.venv-web/bin/pytest apps/web/recipes/tests/test_pending_cookbook.py -v`
Expected: PASS (6 passed).

- [ ] **Step 11: Run the cookbook regression tests**

Run: `.venv-web/bin/pytest apps/web/recipes/tests/test_cookbook.py -v`
Expected: PASS (no regressions in count/empty-state copy). If a cookbook test asserts an exact `total` for a user that also has an in-progress job, it will not — fixtures there create only recipes, so `pending_jobs` is empty and `total` is unchanged.

- [ ] **Step 12: Commit**

```bash
git add apps/web/recipes/views.py apps/web/recipes/urls.py apps/web/templates/recipes/_cookbook_pending_card.html apps/web/templates/recipes/_cookbook_pending_row.html apps/web/templates/recipes/_cookbook.html apps/web/static/css/components.css apps/web/recipes/tests/test_pending_cookbook.py
git commit -m "feat(recipes): show in-progress extractions as cookbook cards"
```

---

## Task 4: Fly-to-cookbook animation

**Files:**
- Create: `apps/web/static/js/extract-fly.js`
- Modify: `apps/web/templates/base.html` (add `{% block scripts %}` before `</body>`)
- Modify: `apps/web/templates/recipes/discover.html` (load the script)
- Modify: `apps/web/recipes/tests/test_landing.py` (smoke: script present on Discover)

**Interfaces:**
- Consumes: `.extract` buttons (in HTMX-swapped results), card containers `.rcard` / `.rrow`, `#saved-tab` with `[data-cookbook-badge]` (Task 1).
- Produces: on `.extract` click, a fixed-position clone animates to the Saved tab; badge text increments by 1 and pops; tab flashes accent. Does not call `preventDefault` (the HTMX POST from Task 2 still fires). Honors `prefers-reduced-motion` (skip flight/pop, still bump the number + reveal a hidden badge).

- [ ] **Step 1: Write the failing smoke test**

In `apps/web/recipes/tests/test_landing.py`, add (adjust the existing auth fixture name if different — reuse whatever logs a user in and hits `/`):

```python
def test_discover_loads_fly_script(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 200
    assert b"js/extract-fly.js" in resp.content
```

If `test_landing.py` has no `auth_client` fixture, add one matching `test_extract.py`'s fixture (create_user with `onboarding_completed=True`, then `client.login`).

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-web/bin/pytest apps/web/recipes/tests/test_landing.py::test_discover_loads_fly_script -v`
Expected: FAIL — script tag not present.

- [ ] **Step 3: Add the `{% block scripts %}` hook to base**

In `apps/web/templates/base.html`, add immediately before the closing `</body>` tag:

```html
  {% block scripts %}{% endblock %}
</body>
```

- [ ] **Step 4: Load the script on Discover**

In `apps/web/templates/recipes/discover.html`, after the `{% endblock %}` that closes `content` (i.e. at the end of the file), add:

```html
{% block scripts %}
<script src="{% static 'js/extract-fly.js' %}"></script>
{% endblock %}
```

And ensure `{% load static %}` is present at the top of `discover.html` (add `{% load static %}` as the second line, after `{% extends "base.html" %}`, if not already there).

- [ ] **Step 5: Create the fly animation module**

Create `apps/web/static/js/extract-fly.js`:

```javascript
(function () {
  var NS = 'http://www.w3.org/2000/svg';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function savedTab() { return document.getElementById('saved-tab'); }
  function badgeOf(tab) { return tab && tab.querySelector('[data-cookbook-badge]'); }

  function bumpBadge(badge, tab) {
    if (!badge) return;
    badge.classList.remove('nav-badge--empty');
    var n = parseInt(badge.textContent, 10) || 0;
    badge.textContent = String(n + 1);
    if (reduce) return;
    badge.animate(
      [
        { transform: 'scale(1)', background: 'var(--accent)', color: 'var(--on-accent)' },
        { transform: 'scale(1.5)', background: 'var(--accent)', color: 'var(--on-accent)' },
        { transform: 'scale(1)' }
      ],
      { duration: 520, easing: 'cubic-bezier(.34,1.56,.64,1)' }
    );
    if (tab) {
      var resting = getComputedStyle(tab).color;
      tab.animate(
        [{ color: 'var(--accent)' }, { color: 'var(--accent)' }, { color: resting }],
        { duration: 700, easing: 'ease-out' }
      );
    }
  }

  function fly(card, tab, badge) {
    var cardRect = card.getBoundingClientRect();
    var tgt = tab.getBoundingClientRect();

    var clone = card.cloneNode(true);
    var s = clone.style;
    s.position = 'fixed'; s.left = cardRect.left + 'px'; s.top = cardRect.top + 'px';
    s.width = cardRect.width + 'px'; s.height = cardRect.height + 'px'; s.margin = '0';
    s.zIndex = '99999'; s.pointerEvents = 'none'; s.boxShadow = 'var(--shadow-2)';
    s.borderRadius = '14px'; s.transformOrigin = 'center center';
    s.willChange = 'transform, opacity';
    document.body.appendChild(clone);

    var dx = tgt.left + tgt.width / 2 - (cardRect.left + cardRect.width / 2);
    var dy = tgt.top + tgt.height / 2 - (cardRect.top + cardRect.height / 2);
    var midX = dx * 0.45;
    var midY = dy * 0.45 - 130;

    card.animate(
      [{ transform: 'scale(1)' }, { transform: 'scale(1.015)' }, { transform: 'scale(1)' }],
      { duration: 260, easing: 'ease-out' }
    );

    var flight = clone.animate(
      [
        { transform: 'translate(0,0) scale(1) rotate(0deg)', opacity: 1, offset: 0 },
        { transform: 'translate(' + midX + 'px,' + midY + 'px) scale(0.46) rotate(-5deg)', opacity: 0.96, offset: 0.55 },
        { transform: 'translate(' + dx + 'px,' + dy + 'px) scale(0.06) rotate(8deg)', opacity: 0, offset: 1 }
      ],
      { duration: 880, easing: 'cubic-bezier(.55,0,.7,.25)' }
    );

    var done = false;
    function finish() {
      if (done) return;
      done = true;
      clone.remove();
      bumpBadge(badge, tab);
    }
    flight.onfinish = finish;
    setTimeout(finish, 940);
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('.extract');
    if (!btn || btn.dataset.flying) return;
    var tab = savedTab();
    var badge = badgeOf(tab);
    var card = btn.closest('.rcard, .rrow');
    if (!tab || !card) return;        // let HTMX proceed unenhanced
    btn.dataset.flying = '1';         // guard double-fire; do NOT preventDefault
    if (reduce) { bumpBadge(badge, tab); return; }
    fly(card, tab, badge);
  }, true);
})();
```

- [ ] **Step 6: Run the smoke test**

Run: `.venv-web/bin/pytest apps/web/recipes/tests/test_landing.py -v`
Expected: PASS.

- [ ] **Step 7: Visual verification (running-web-app skill)**

Use the `running-web-app` skill to launch `apps/web`, log in, run a search that returns extractable videos, and confirm by screenshot:
1. Clicking **Extract** flies a shrinking/fading clone up into the **Saved** tab.
2. The Saved badge pops and increments (e.g. 12 → 13).
3. The button settles to the **In cookbook** check state (no redirect; you stay on results).
4. Visiting **Saved** shows the recipe as an **EXTRACTING…** card; when the job finishes it becomes the real recipe card.

Document the screenshots; if any step misbehaves, fix before committing.

- [ ] **Step 8: Commit**

```bash
git add apps/web/static/js/extract-fly.js apps/web/templates/base.html apps/web/templates/recipes/discover.html apps/web/recipes/tests/test_landing.py
git commit -m "feat(recipes): fly-to-cookbook animation + badge pop on Extract"
```

---

## Final verification

- [ ] Run the full recipes suite: `.venv-web/bin/pytest apps/web/recipes/tests/ -q` — all green.
- [ ] `git log --oneline origin/main..HEAD` shows the 4 feature commits (+ the spec/plan docs).
- [ ] Open a PR targeting `main` (per global rule — never stack; base is `main`).

## Self-review notes (spec coverage)

- §A nav badge → Task 1. §B fly JS → Task 4. §C extract "In cookbook" partial → Task 2. §D pending cards + `cookbook_job_card` poll → Task 3. Testing rows → tests in Tasks 1-4. All spec sections covered.
- Refinement vs spec: badge is rendered (hidden) at 0 rather than fully omitted, so the optimistic +1 has a node to reveal — same visual result (no badge at 0). Pending placeholders are gated on `not has_filters` (q / facets / fav), not also on sort — placeholders are pinned at the top regardless of sort order, which is simpler and matches intent.
