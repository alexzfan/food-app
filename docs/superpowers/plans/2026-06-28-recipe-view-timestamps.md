# Recipe View + step→video timestamps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the bare recipe detail page with the Mise "Recipe View" whose method steps, when tapped, seek the embedded YouTube video — backed by a new transcript-timestamp pipeline.

**Architecture:** Captions are fetched with their per-snippet start times preserved as `[seconds] text` lines; the extraction prompt gains a nullable integer `start` per instruction; `Recipe` stores the transcript and the timestamped instructions; the rebuilt Django template drives a YouTube IFrame API player from an Alpine component (tap-to-seek + active-step sync). Everything degrades gracefully when there is no video or no timestamps.

**Tech Stack:** Django templates + htmx + Alpine.js (web, `.venv-web`); FastAPI extraction service (`apps/audio-service`, `.venv-ml`); YouTube IFrame Player API; `youtube-transcript-api`.

## Global Constraints

- **Web tests:** `cd apps/web && ../../.venv-web/bin/pytest <path> -v` (pytest rootdir is `apps/web`; pytest-django, `db` fixture applies migrations).
- **ML tests:** `cd apps/audio-service && ../../.venv-ml/bin/pytest <path> -v`.
- **Migrations:** `cd apps/web && ../../.venv-web/bin/python manage.py makemigrations recipes`.
- **Branch:** `feat/recipe-view-timestamps`, PR into `main`. Do not stack on other branches.
- **`main` has no `Video` model and no `youtube.seconds_to_display`** (both live only on the unmerged cache branch). Do not reference them. Format seconds with the new `views._mmss` helper.
- **`start` is best-effort and nullable everywhere.** Non-YouTube sources and pre-existing recipes must render correctly with all `start = null`.
- Reuse existing CSS tokens in `static/css/tokens.css`; add **no new colors**. `[x-cloak]` is already defined (`components.css:286`).
- Commit after each task's tests pass.

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `apps/web/recipes/youtube.py` | modify `fetch_transcript` | emit `[seconds] text` transcript lines |
| `apps/audio-service/app/prompt.py` | modify | add `start` to instruction schema + guideline |
| `apps/audio-service/app/extractor.py` | modify `parse_recipe_response` | coerce each instruction `start` to `int\|None` |
| `apps/web/recipes/models.py` | modify `Recipe` | add `transcript` TextField; update `instructions` comment |
| `apps/web/recipes/migrations/0003_recipe_transcript.py` | create (generated) | DB migration for the field |
| `apps/web/recipes/tasks.py` | modify `run_extraction_job` | persist transcript on the recipe |
| `apps/web/recipes/views.py` | add `_mmss`, modify `recipe_detail` | build `steps` + `rv_data` context |
| `apps/web/templates/recipes/detail.html` | rewrite | the Recipe View + Alpine/YT player |
| `apps/web/templates/recipes/_favorite_button.html` | restyle | design-matched Save pill |
| `apps/web/static/css/components.css` | append | `.recipe-view` styles |
| `apps/web/recipes/tests/test_youtube.py` | modify one test | timestamped transcript |
| `apps/audio-service/tests/test_extractor.py` | add tests | prompt + start coercion |
| `apps/web/recipes/tests/test_models.py` | add test | transcript default |
| `apps/web/recipes/tests/test_tasks.py` | add test | transcript persisted |
| `apps/web/recipes/tests/test_recipe_view.py` | create | view context + template render |
| `apps/web/recipes/tests/test_pages.py` | modify one test | new Save label |

---

### Task 1: Timestamped transcript

**Files:**
- Modify: `apps/web/recipes/youtube.py` (`fetch_transcript`, ~lines 135-140)
- Test: `apps/web/recipes/tests/test_youtube.py` (replace `test_fetch_transcript_joins_segments`)

**Interfaces:**
- Produces: `fetch_transcript(video_id) -> str | None` — newline-joined `"[<int start>] <text>"` lines, or `None` when empty/failed (unchanged error contract).

- [ ] **Step 1: Replace the existing transcript-join test**

In `apps/web/recipes/tests/test_youtube.py`, replace `test_fetch_transcript_joins_segments` with:

```python
def test_fetch_transcript_includes_timestamps():
    from youtube_transcript_api import FetchedTranscriptSnippet

    snippets = [
        FetchedTranscriptSnippet(text="boil water", start=0.0, duration=1.0),
        FetchedTranscriptSnippet(text="add pasta", start=12.7, duration=1.0),
    ]
    with patch(
        "recipes.youtube.YouTubeTranscriptApi.fetch", return_value=snippets
    ):
        text = youtube.fetch_transcript("vid")
    assert text == "[0] boil water\n[12] add pasta"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_youtube.py::test_fetch_transcript_includes_timestamps -v`
Expected: FAIL (current output is space-joined `"boil water add pasta"`).

- [ ] **Step 3: Build timestamped lines in `fetch_transcript`**

In `apps/web/recipes/youtube.py`, inside `fetch_transcript`'s `try`, replace:

```python
        fetched = YouTubeTranscriptApi().fetch(video_id)
        text = " ".join(snippet.text for snippet in fetched).strip()
        if not text:
```

with:

```python
        fetched = YouTubeTranscriptApi().fetch(video_id)
        lines = [
            f"[{int(snippet.start)}] {snippet.text.strip()}"
            for snippet in fetched
            if snippet.text and snippet.text.strip()
        ]
        text = "\n".join(lines).strip()
        if not text:
```

- [ ] **Step 4: Run the youtube tests**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_youtube.py -v`
Expected: PASS (including the unchanged `test_fetch_transcript_returns_none_on_error` and empty-body test).

- [ ] **Step 5: Commit**

```bash
git add apps/web/recipes/youtube.py apps/web/recipes/tests/test_youtube.py
git commit -m "feat(recipes): preserve caption timestamps in fetch_transcript"
```

---

### Task 2: Prompt `start` field + parse coercion

**Files:**
- Modify: `apps/audio-service/app/prompt.py`
- Modify: `apps/audio-service/app/extractor.py` (`parse_recipe_response`)
- Test: `apps/audio-service/tests/test_extractor.py`

**Interfaces:**
- Consumes: timestamped transcript lines from Task 1 (`[seconds] text`).
- Produces: `parse_recipe_response(text) -> dict` where every `instructions[i]["start"]` is `int | None`.

- [ ] **Step 1: Write failing tests**

Append to `apps/audio-service/tests/test_extractor.py`:

```python
def test_prompt_advertises_start_field():
    from app.prompt import RECIPE_EXTRACTION_PROMPT, build_prompt

    assert '"start"' in RECIPE_EXTRACTION_PROMPT
    assert "start" in build_prompt("[0] boil", None)


def test_parse_coerces_instruction_start():
    raw = (
        '{"title": "Noodles", "instructions": ['
        '{"step": 1, "text": "a", "start": "12"},'
        '{"step": 2, "text": "b", "start": 13.9},'
        '{"step": 3, "text": "c", "start": "nope"},'
        '{"step": 4, "text": "d"}]}'
    )
    starts = [s.get("start") for s in parse_recipe_response(raw)["instructions"]]
    assert starts == [12, 13, None, None]
```

- [ ] **Step 2: Run and watch them fail**

Run: `cd apps/audio-service && ../../.venv-ml/bin/pytest tests/test_extractor.py::test_prompt_advertises_start_field tests/test_extractor.py::test_parse_coerces_instruction_start -v`
Expected: FAIL (`"start"` absent from prompt; `start` not coerced).

- [ ] **Step 3: Add `start` to the prompt**

In `apps/audio-service/app/prompt.py`, change the instructions line of the schema from:

```python
  "instructions": [
    {"step": 1, "text": "Clear instruction text", "duration": "time if mentioned (optional)"}
  ],
```

to:

```python
  "instructions": [
    {"step": 1, "text": "Clear instruction text", "start": 12, "duration": "time if mentioned (optional)"}
  ],
```

And in the same file's `Guidelines:` block, add this bullet after `- Number instructions sequentially`:

```
- Each transcript line may be prefixed with its start time in seconds in square brackets, e.g. "[12] add the garlic". Set each instruction's "start" to the integer seconds tag of the line where that step begins. Use null when the transcript has no timestamps or the moment is unclear.
```

- [ ] **Step 4: Coerce `start` in `parse_recipe_response`**

In `apps/audio-service/app/extractor.py`, add this helper above `parse_recipe_response`:

```python
def _coerce_start(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
```

Then, in `parse_recipe_response`, just before `return recipe`, add:

```python
    for step in recipe["instructions"]:
        if isinstance(step, dict):
            step["start"] = _coerce_start(step.get("start"))
```

- [ ] **Step 5: Run the extractor tests**

Run: `cd apps/audio-service && ../../.venv-ml/bin/pytest tests/test_extractor.py -v`
Expected: PASS (all, including the pre-existing parse/extractor tests).

- [ ] **Step 6: Commit**

```bash
git add apps/audio-service/app/prompt.py apps/audio-service/app/extractor.py apps/audio-service/tests/test_extractor.py
git commit -m "feat(ml): extract per-step start timestamps from captions"
```

---

### Task 3: Persist the transcript on `Recipe`

**Files:**
- Modify: `apps/web/recipes/models.py` (`Recipe`)
- Create: `apps/web/recipes/migrations/0003_recipe_transcript.py` (generated)
- Modify: `apps/web/recipes/tasks.py` (`run_extraction_job`)
- Test: `apps/web/recipes/tests/test_models.py`, `apps/web/recipes/tests/test_tasks.py`

**Interfaces:**
- Produces: `Recipe.transcript: str` (default `""`); `run_extraction_job` writes `transcript=transcript or ""`.

- [ ] **Step 1: Write failing tests**

Append to `apps/web/recipes/tests/test_models.py`:

```python
def test_recipe_transcript_defaults_blank(user):
    r = Recipe.objects.create(owner=user, title="Pasta")
    assert r.transcript == ""
```

Append to `apps/web/recipes/tests/test_tasks.py`:

```python
def test_extraction_stores_transcript(user):
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.PASTE_TRANSCRIPT, title="Pasta"
    )
    summary = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}
    with patch("recipes.tasks.ml_client.extract", return_value=summary):
        run_extraction_job(job.id, transcript="[0] boil pasta")
    job.refresh_from_db()
    assert Recipe.objects.get(pk=job.recipe_id).transcript == "[0] boil pasta"
```

- [ ] **Step 2: Run and watch them fail**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_models.py::test_recipe_transcript_defaults_blank recipes/tests/test_tasks.py::test_extraction_stores_transcript -v`
Expected: FAIL (`Recipe` has no `transcript` attribute / column).

- [ ] **Step 3: Add the field and update the comment**

In `apps/web/recipes/models.py`, change:

```python
    instructions = models.JSONField(default=list)  # [{step, text, duration?}]
```

to:

```python
    instructions = models.JSONField(default=list)  # [{step, text, start?, duration?}]
```

And add this field immediately after the `difficulty` field (before `created_at`):

```python
    transcript = models.TextField(blank=True, default="")  # source transcript; [seconds]-tagged for YouTube captions
```

- [ ] **Step 4: Generate the migration**

Run: `cd apps/web && ../../.venv-web/bin/python manage.py makemigrations recipes`
Expected: creates `recipes/migrations/0003_recipe_transcript.py` adding `transcript` (non-interactive — the field has `default=""`).

- [ ] **Step 5: Persist the transcript in the task**

In `apps/web/recipes/tasks.py`, inside `run_extraction_job`'s `Recipe.objects.create(...)`, add this keyword argument (e.g. right after `youtube_video_id=job.youtube_video_id,`):

```python
            transcript=transcript or "",
```

- [ ] **Step 6: Run the tests**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_models.py recipes/tests/test_tasks.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/web/recipes/models.py apps/web/recipes/migrations/0003_recipe_transcript.py apps/web/recipes/tasks.py apps/web/recipes/tests/test_models.py apps/web/recipes/tests/test_tasks.py
git commit -m "feat(recipes): store source transcript on Recipe"
```

---

### Task 4: `recipe_detail` builds step + player context

**Files:**
- Modify: `apps/web/recipes/views.py` (add `_mmss`, rewrite `recipe_detail`)
- Test: `apps/web/recipes/tests/test_recipe_view.py` (create)

**Interfaces:**
- Produces context: `recipe`; `steps: list[{number:int, text:str, start:int|None, start_display:str}]`; `rv_data: {"videoId": str, "steps": list[int|None]}`.
- `_mmss(seconds: int|None) -> str` — `135 → "2:15"`, `12 → "0:12"`, `None → ""`.

- [ ] **Step 1: Create the view-context test**

Create `apps/web/recipes/tests/test_recipe_view.py`:

```python
import pytest
from django.contrib.auth import get_user_model

from recipes.models import Recipe

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


def test_recipe_detail_builds_step_context(auth_client, user):
    r = Recipe.objects.create(
        owner=user, title="Garlic Noodles", youtube_video_id="abc123",
        instructions=[
            {"step": 1, "text": "Boil", "start": 12},
            {"step": 2, "text": "Melt", "start": 108},
            {"step": 3, "text": "Toss"},
        ],
    )
    resp = auth_client.get(f"/recipes/{r.id}/")
    assert resp.status_code == 200
    steps = resp.context["steps"]
    assert [s["start"] for s in steps] == [12, 108, None]
    assert steps[0]["start_display"] == "0:12"
    assert steps[1]["start_display"] == "1:48"
    assert steps[2]["start_display"] == ""
    assert resp.context["rv_data"] == {"videoId": "abc123", "steps": [12, 108, None]}
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_recipe_view.py -v`
Expected: FAIL (`KeyError: 'steps'` — context not yet provided).

- [ ] **Step 3: Add `_mmss` and rewrite `recipe_detail`**

In `apps/web/recipes/views.py`, add this module-level helper (near the other top-level helpers, e.g. after `_remember_search`):

```python
def _mmss(seconds):
    """Whole seconds -> "m:ss" display, or "" for None. e.g. 135 -> "2:15"."""
    if seconds is None:
        return ""
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"
```

Replace the body of `recipe_detail` with:

```python
@login_required
@onboarding_required
def recipe_detail(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, owner=request.user)
    recipe.is_favorite = Favorite.objects.filter(
        user=request.user, recipe=recipe
    ).exists()

    steps, starts = [], []
    for i, step in enumerate(recipe.instructions, start=1):
        start = step.get("start") if isinstance(step, dict) else None
        if isinstance(start, bool) or not isinstance(start, int):
            start = None
        text = step.get("text", "") if isinstance(step, dict) else str(step)
        steps.append(
            {"number": i, "text": text, "start": start, "start_display": _mmss(start)}
        )
        starts.append(start)

    rv_data = {"videoId": recipe.youtube_video_id, "steps": starts}
    return render(
        request,
        "recipes/detail.html",
        {"recipe": recipe, "steps": steps, "rv_data": rv_data},
    )
```

- [ ] **Step 4: Run the test**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_recipe_view.py -v`
Expected: PASS (the existing bare template ignores the new context, so it still renders).

- [ ] **Step 5: Commit**

```bash
git add apps/web/recipes/views.py apps/web/recipes/tests/test_recipe_view.py
git commit -m "feat(recipes): build step + player context for recipe view"
```

---

### Task 5: Recipe View template + CSS + Save button

**Files:**
- Rewrite: `apps/web/templates/recipes/detail.html`
- Restyle: `apps/web/templates/recipes/_favorite_button.html`
- Append: `apps/web/static/css/components.css`
- Test: `apps/web/recipes/tests/test_recipe_view.py` (append render tests)
- Modify: `apps/web/recipes/tests/test_pages.py` (`test_detail_favorite_returns_button_not_card`)

**Interfaces:**
- Consumes Task 4 context (`recipe`, `steps`, `rv_data`).
- The `#rv-data` `json_script` block feeds the Alpine `recipeView()` component (`starts` array + `videoId`).

- [ ] **Step 1: Write the render tests**

Append to `apps/web/recipes/tests/test_recipe_view.py`:

```python
def test_recipe_view_renders_jump_chips(auth_client, user):
    r = Recipe.objects.create(
        owner=user, title="Garlic Noodles", youtube_video_id="abc123",
        channel_name="Lan's Kitchen",
        instructions=[{"step": 1, "text": "Boil noodles", "start": 12}],
    )
    resp = auth_client.get(f"/recipes/{r.id}/")
    body = resp.content
    assert b"Boil noodles" in body
    assert b"JUMP TO 0:12" in body
    assert b"Start cooking" in body
    assert b"Share" in body
    assert b'id="yt-player"' in body


def test_recipe_view_without_video_has_no_chip_or_player(auth_client, user):
    r = Recipe.objects.create(
        owner=user, title="Plain", instructions=[{"step": 1, "text": "Stir well"}]
    )
    resp = auth_client.get(f"/recipes/{r.id}/")
    body = resp.content
    assert resp.status_code == 200
    assert b"Stir well" in body
    assert b"JUMP TO" not in body
    assert b'id="yt-player"' not in body
```

- [ ] **Step 2: Run and watch them fail**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_recipe_view.py -v`
Expected: FAIL on the two new tests (old template has no chips/player/buttons).

- [ ] **Step 3: Restyle the Save button partial**

Replace the entire contents of `apps/web/templates/recipes/_favorite_button.html` with:

```html
<form hx-post="{% url 'toggle_favorite' recipe.id %}" hx-target="this" hx-swap="outerHTML">
  {% csrf_token %}
  <input type="hidden" name="context" value="detail">
  <button type="submit" class="rv-btn rv-btn--{% if recipe.is_favorite %}fav{% else %}secondary{% endif %}">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="{% if recipe.is_favorite %}currentColor{% else %}none{% endif %}" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>
    {% if recipe.is_favorite %}Saved{% else %}Save recipe{% endif %}
  </button>
</form>
```

- [ ] **Step 4: Rewrite the detail template**

Replace the entire contents of `apps/web/templates/recipes/detail.html` with:

```html
{% extends "base.html" %}
{% block title %}{{ recipe.title }}{% endblock %}
{% block content %}
{{ rv_data|json_script:"rv-data" }}
<div class="recipe-view" x-data="recipeView()" x-init="init()">

  <a class="rv-back" href="{% url 'discover' %}">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"></path></svg>
    BACK TO RESULTS
  </a>

  <div class="rv-header">
    <div class="rv-header__main">
      <div class="rv-badges">
        <span class="rv-badge rv-badge--ai">AI EXTRACTED</span>
        {% if recipe.channel_name %}<span class="rv-badge rv-badge--source">{{ recipe.channel_name }}</span>{% endif %}
      </div>
      <h1 class="rv-title">{{ recipe.title }}</h1>
      {% if recipe.description %}<p class="rv-desc">{{ recipe.description }}</p>{% endif %}
      <div class="rv-meta">
        {% if recipe.cook_time_minutes %}<span class="rv-meta__item"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path></svg>{{ recipe.cook_time_minutes }} MIN</span>{% endif %}
        {% if recipe.servings %}<span class="rv-meta__item"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle></svg>SERVES {{ recipe.servings }}</span>{% endif %}
        {% if recipe.difficulty %}<span class="rv-meta__item"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.4-.5-2-1-3-1.1-2.1-.2-4 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.2.4-2.3 1-3a2.5 2.5 0 0 0 2.5 2.5z"></path></svg>{{ recipe.difficulty|upper }}</span>{% endif %}
      </div>
    </div>

    <div class="rv-actions">
      <div class="rv-actions__default" x-show="!cooking">
        <button class="rv-btn rv-btn--primary" @click="startCooking()">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 2v7c0 1.1.9 2 2 2a2 2 0 0 0 2-2V2"></path><path d="M7 2v20"></path><path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"></path></svg>
          Start cooking
        </button>
        {% include "recipes/_favorite_button.html" with recipe=recipe %}
        <button class="rv-btn rv-btn--secondary" @click="share()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.6" y1="13.5" x2="15.4" y2="17.5"></line><line x1="15.4" y1="6.5" x2="8.6" y2="10.5"></line></svg>
          Share
        </button>
        <div class="rv-toast" x-show="shared" x-cloak>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg>
          Link copied
        </div>
      </div>
      <div class="rv-cookbar" x-show="cooking" x-cloak>
        <span class="rv-cookbar__label" x-text="'STEP ' + ((active == null ? 0 : active) + 1) + ' OF ' + {{ steps|length }}"></span>
        <button class="rv-cook-btn" @click="prev()" aria-label="Previous step"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"></path></svg></button>
        <button class="rv-cook-btn rv-cook-btn--next" @click="next()" aria-label="Next step"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"></path></svg></button>
        <button class="rv-cook-btn rv-cook-btn--exit" @click="exitCook()" aria-label="Exit cooking mode"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg></button>
      </div>
    </div>
  </div>

  <div class="rv-grid">
    <div class="rv-left">
      {% if recipe.youtube_video_id %}
      <div class="rv-video"><div id="yt-player"></div></div>
      {% endif %}
      <div class="rv-credit">
        <span class="rv-credit__avatar"></span>
        <div class="rv-credit__meta">
          <div class="rv-credit__name">{{ recipe.channel_name|default:"Unknown channel" }}</div>
        </div>
        {% if recipe.youtube_video_id %}
        <a class="rv-credit__yt" href="https://www.youtube.com/watch?v={{ recipe.youtube_video_id }}" target="_blank" rel="noopener">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="#FF0000"><path d="M21.6 7.2s-.2-1.4-.8-2c-.8-.8-1.7-.8-2.1-.9C15.8 4.1 12 4.1 12 4.1s-3.8 0-6.7.2c-.4.1-1.3.1-2.1.9-.6.6-.8 2-.8 2S2.1 8.8 2.1 10.5v1.6c0 1.6.2 3.3.2 3.3s.2 1.4.8 2c.8.8 1.8.8 2.3.9 1.7.2 6.6.2 6.6.2s3.8 0 6.7-.2c.4-.1 1.3-.1 2.1-.9.6-.6.8-2 .8-2s.2-1.6.2-3.3v-1.6c0-1.6-.2-3.3-.2-3.3zM9.9 14.3V8.6l5 2.9-5 2.8z"></path></svg>
          YouTube
        </a>
        {% endif %}
      </div>

      <div class="rv-ings__head">
        <h3 class="rv-h3">Ingredients</h3>
        {% if recipe.servings %}<span class="rv-serves">SERVES {{ recipe.servings }}</span>{% endif %}
      </div>
      <div class="rv-ings">
        {% for ing in recipe.ingredients %}
        <label class="rv-ing">
          <input type="checkbox" class="rv-ing__check">
          <span class="rv-ing__amount">{{ ing.amount }}{% if ing.unit %} {{ ing.unit }}{% endif %}</span>
          <span class="rv-ing__name">{{ ing.name }}{% if ing.notes %}, {{ ing.notes }}{% endif %}</span>
        </label>
        {% empty %}
        <div class="rv-ing"><span class="rv-ing__name">No ingredients listed.</span></div>
        {% endfor %}
      </div>
    </div>

    <div class="rv-right">
      <div class="rv-method__head">
        <h3 class="rv-h3">Method</h3>
        {% if recipe.youtube_video_id %}<span class="rv-method__hint">TAP A STEP TO JUMP THE VIDEO</span>{% endif %}
      </div>
      <div class="rv-steps">
        {% for step in steps %}
        <div class="rv-step" :class="{ 'rv-step--active': active === {{ forloop.counter0 }} }" @click="onStep({{ forloop.counter0 }})">
          <span class="rv-step__num" :class="{ 'rv-step__num--active': active === {{ forloop.counter0 }} }">{{ step.number }}</span>
          <div class="rv-step__body">
            <p class="rv-step__text">{{ step.text }}</p>
            {% if recipe.youtube_video_id and step.start is not None %}
            <span class="rv-chip" :class="{ 'rv-chip--active': active === {{ forloop.counter0 }} }">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"></polygon></svg>
              <span x-text="active === {{ forloop.counter0 }} ? 'PLAYING · {{ step.start_display }}' : 'JUMP TO {{ step.start_display }}'">JUMP TO {{ step.start_display }}</span>
            </span>
            {% endif %}
          </div>
        </div>
        {% endfor %}
      </div>
    </div>
  </div>
</div>

<script>
function recipeView() {
  const data = JSON.parse(document.getElementById('rv-data').textContent);
  return {
    starts: data.steps,
    videoId: data.videoId,
    hasVideo: !!data.videoId,
    active: null, cooking: false, shared: false,
    player: null, _timer: null, _poll: null, _sh: null,
    init() { if (this.hasVideo) this.loadPlayer(); },
    loadPlayer() {
      const make = () => this.createPlayer();
      if (window.YT && window.YT.Player) { make(); return; }
      if (!window._ytApiLoading) {
        window._ytApiLoading = true;
        const tag = document.createElement('script');
        tag.src = 'https://www.youtube.com/iframe_api';
        document.head.appendChild(tag);
      }
      this._poll = setInterval(() => {
        if (window.YT && window.YT.Player) { clearInterval(this._poll); make(); }
      }, 200);
    },
    createPlayer() {
      if (this.player) return;
      this.player = new YT.Player('yt-player', {
        videoId: this.videoId,
        playerVars: { rel: 0, modestbranding: 1, playsinline: 1 },
        width: '100%', height: '100%',
      });
      this._timer = setInterval(() => this.tick(), 500);
    },
    tick() {
      if (!this.player || !this.player.getPlayerState) return;
      if (this.player.getPlayerState() !== 1) return;
      const t = this.player.getCurrentTime();
      let idx = null;
      this.starts.forEach((s, i) => { if (s != null && s <= t + 0.4) idx = i; });
      if (idx != null && idx !== this.active) this.active = idx;
    },
    seek(sec) {
      if (this.player && this.player.seekTo) { this.player.seekTo(sec, true); this.player.playVideo(); }
    },
    onStep(i) {
      this.active = i;
      const s = this.starts[i];
      if (this.hasVideo && s != null) this.seek(s);
    },
    startCooking() { this.cooking = true; this.onStep(0); },
    exitCook() { this.cooking = false; },
    next() { const n = Math.min((this.active == null ? 0 : this.active) + 1, this.starts.length - 1); this.onStep(n); },
    prev() { const n = Math.max((this.active == null ? 0 : this.active) - 1, 0); this.onStep(n); },
    share() {
      if (navigator.clipboard) navigator.clipboard.writeText(location.href);
      this.shared = true; clearTimeout(this._sh);
      this._sh = setTimeout(() => { this.shared = false; }, 1800);
    },
  };
}
</script>
{% endblock %}
```

- [ ] **Step 5: Append the Recipe View CSS**

Append to `apps/web/static/css/components.css`:

```css
/* ---- Recipe View (detail) --------------------------------------------- */
.recipe-view { max-width: 1180px; margin: 0 auto; }
.rv-back { display: inline-flex; align-items: center; gap: 7px; font-family: var(--font-mono); font-size: 11px; letter-spacing: .08em; color: var(--muted); margin-bottom: 22px; }
.rv-back:hover { color: var(--accent); }

.rv-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 36px; }
.rv-header__main { flex: 1; min-width: 0; }
.rv-badges { display: flex; gap: 9px; margin-bottom: 16px; flex-wrap: wrap; }
.rv-badge { display: inline-flex; align-items: center; padding: 5px 11px; border-radius: var(--r-pill); font-family: var(--font-mono); font-size: 11px; font-weight: 500; letter-spacing: .06em; }
.rv-badge--ai { background: var(--accent-soft); color: var(--on-soft); border: 1px solid var(--accent-line); }
.rv-badge--source { background: var(--surface); color: var(--ink-2); border: 1px solid var(--line-2); }
.rv-title { font-family: var(--font-display); font-weight: 400; font-size: 44px; line-height: 1.05; letter-spacing: -.015em; margin: 0 0 14px; color: var(--ink); }
.rv-desc { font-size: 16px; line-height: 1.6; color: var(--ink-2); max-width: 580px; margin: 0 0 18px; }
.rv-meta { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; font-family: var(--font-mono); font-size: 12.5px; color: var(--ink-2); }
.rv-meta__item { display: inline-flex; align-items: center; gap: 7px; }

.rv-actions { width: 220px; flex: 0 0 auto; }
.rv-actions__default { display: flex; flex-direction: column; gap: 10px; }
.rv-actions form { margin: 0; }
.rv-btn { display: inline-flex; align-items: center; justify-content: center; gap: 9px; width: 100%; padding: 12px 20px; border-radius: var(--r-pill); font-family: var(--font-ui); font-weight: 600; font-size: 15px; line-height: 1; cursor: pointer; border: 1px solid transparent; white-space: nowrap; }
.rv-btn--primary { background: var(--accent); color: var(--on-accent); box-shadow: var(--shadow-1); }
.rv-btn--primary:hover { background: var(--accent-press); }
.rv-btn--secondary { background: var(--surface); color: var(--ink); border-color: var(--line-2); }
.rv-btn--secondary:hover { background: var(--surface-2); }
.rv-btn--fav { background: var(--accent-soft); color: var(--on-soft); border-color: var(--accent-line); }

.rv-cookbar { display: flex; align-items: center; gap: 8px; border: 1px solid var(--accent-line); background: var(--accent-soft); border-radius: var(--r-lg); padding: 12px; }
.rv-cookbar__label { flex: 1; font-family: var(--font-mono); font-size: 11px; letter-spacing: .08em; color: var(--on-soft); font-weight: 600; }
.rv-cook-btn { width: 36px; height: 36px; border-radius: 50%; border: 1px solid var(--line-2); background: var(--surface); color: var(--ink); cursor: pointer; display: inline-flex; align-items: center; justify-content: center; }
.rv-cook-btn--next { border-color: transparent; background: var(--accent); color: var(--on-accent); }
.rv-cook-btn--exit { border-color: transparent; background: transparent; color: var(--on-soft); }

.rv-toast { display: inline-flex; align-items: center; gap: 7px; margin-top: 4px; padding: 9px 14px; border-radius: var(--r-pill); background: var(--ink); color: var(--paper); font-size: 12.5px; font-weight: 600; }

.rv-grid { display: grid; grid-template-columns: 460px 1fr; gap: 38px; margin-top: 32px; align-items: start; }
.rv-left { position: sticky; top: 20px; }
.rv-video { position: relative; aspect-ratio: 16 / 9; border-radius: var(--r-md); overflow: hidden; background: #0c0a08; box-shadow: var(--shadow-1); border: 1px solid var(--line); }
.rv-video #yt-player, .rv-video iframe { width: 100%; height: 100%; border: 0; }
.rv-credit { display: flex; align-items: center; gap: 11px; margin: 14px 0 26px; }
.rv-credit__avatar { width: 36px; height: 36px; border-radius: 50%; background: var(--secondary-soft); border: 1px solid var(--line); flex: 0 0 auto; }
.rv-credit__meta { flex: 1; min-width: 0; }
.rv-credit__name { font-size: 14px; color: var(--ink); font-weight: 600; }
.rv-credit__yt { display: inline-flex; align-items: center; gap: 7px; padding: 8px 13px; border-radius: var(--r-pill); border: 1px solid var(--line-2); background: var(--surface); color: var(--ink-2); font-size: 12.5px; font-weight: 600; }

.rv-ings__head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.rv-h3 { font-family: var(--font-display); font-weight: 600; font-size: 22px; margin: 0; color: var(--ink); }
.rv-serves { font-family: var(--font-mono); font-size: 11.5px; letter-spacing: .06em; color: var(--ink-2); border: 1px solid var(--line-2); border-radius: var(--r-pill); background: var(--surface); padding: 6px 12px; }
.rv-ings { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-md); padding: 4px 16px; box-shadow: var(--shadow-1); }
.rv-ing { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--line); cursor: pointer; }
.rv-ing:last-child { border-bottom: 0; }
.rv-ing__check { width: 18px; height: 18px; accent-color: var(--accent); flex: 0 0 auto; }
.rv-ing__amount { font-family: var(--font-mono); font-size: 12.5px; color: var(--on-soft); min-width: 64px; }
.rv-ing__name { font-size: 14.5px; color: var(--ink); }
.rv-ing__check:checked ~ .rv-ing__amount { color: var(--muted); }
.rv-ing__check:checked ~ .rv-ing__name { text-decoration: line-through; color: var(--muted); }

.rv-method__head { display: flex; align-items: baseline; gap: 14px; margin-bottom: 18px; }
.rv-method__hint { font-family: var(--font-mono); font-size: 10.5px; letter-spacing: .12em; color: var(--muted); }
.rv-steps { display: flex; flex-direction: column; gap: 12px; }
.rv-step { display: flex; gap: 16px; padding: 16px 18px; border-radius: var(--r-md); border: 1px solid var(--line); background: var(--surface); cursor: pointer; transition: background .15s ease, border-color .15s ease, box-shadow .15s ease; }
.rv-step--active { border-color: var(--accent-line); background: var(--accent-soft); box-shadow: var(--shadow-1); }
.rv-step__num { flex: 0 0 auto; width: 34px; height: 34px; border-radius: 50%; background: var(--accent-soft); color: var(--on-soft); display: inline-flex; align-items: center; justify-content: center; font-family: var(--font-display); font-size: 17px; font-weight: 600; }
.rv-step__num--active { background: var(--accent); color: var(--on-accent); }
.rv-step__body { flex: 1; min-width: 0; }
.rv-step__text { margin: 0 0 11px; font-size: 16px; line-height: 1.6; color: var(--ink); }
.rv-chip { display: inline-flex; align-items: center; gap: 6px; padding: 5px 11px; border-radius: var(--r-pill); font-family: var(--font-mono); font-size: 11px; font-weight: 500; letter-spacing: .04em; border: 1px solid var(--accent-line); background: transparent; color: var(--accent); }
.rv-chip--active { border-color: var(--accent); background: var(--accent); color: var(--on-accent); }

@media (max-width: 880px) {
  .rv-header { flex-direction: column; gap: 18px; }
  .rv-actions { width: 100%; }
  .rv-actions__default { flex-direction: row; flex-wrap: wrap; }
  .rv-actions__default .rv-btn, .rv-actions form { flex: 1; }
  .rv-btn { width: 100%; }
  .rv-grid { grid-template-columns: 1fr; gap: 24px; }
  .rv-left { position: static; }
  .rv-title { font-size: 32px; }
}
```

- [ ] **Step 6: Update the Save-button assertion in test_pages**

In `apps/web/recipes/tests/test_pages.py`, replace the body of `test_detail_favorite_returns_button_not_card` with:

```python
def test_detail_favorite_returns_button_not_card(auth_client, user):
    r = Recipe.objects.create(owner=user, title="Pasta")
    resp = auth_client.post(f"/recipes/{r.id}/favorite/", {"context": "detail"})
    assert Favorite.objects.filter(user=user, recipe=r).exists()
    # detail context swaps the styled Save button (now reads "Saved"), not a card link
    assert b"Saved" in resp.content
    assert f'href="/recipes/{r.id}/"'.encode() not in resp.content
```

- [ ] **Step 7: Run the affected tests**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_recipe_view.py recipes/tests/test_pages.py -v`
Expected: PASS.

- [ ] **Step 8: Run the full web + ml suites**

Run: `cd apps/web && ../../.venv-web/bin/pytest -q`
Expected: PASS (all).
Run: `cd apps/audio-service && ../../.venv-ml/bin/pytest -q`
Expected: PASS (all).

- [ ] **Step 9: Commit**

```bash
git add apps/web/templates/recipes/detail.html apps/web/templates/recipes/_favorite_button.html apps/web/static/css/components.css apps/web/recipes/tests/test_recipe_view.py apps/web/recipes/tests/test_pages.py
git commit -m "feat(recipes): Mise Recipe View with tap-to-seek method steps"
```

---

### Task 6: Visual verification

**Files:** none (manual check).

- [ ] **Step 1: Launch + screenshot the recipe view**

Use the `running-web-app` skill (`apps/web/.claude/skills/running-web-app/SKILL.md`) to start the Django app and capture the recipe detail page for a recipe that has a `youtube_video_id` and instructions with `start` values. Create one via the Django shell or an existing extracted recipe.

- [ ] **Step 2: Verify against the design**

Confirm: header badges/title/meta; video renders; tapping a method step highlights it (accent) and seeks the player; the active step auto-highlights during playback; "Start cooking" toggles the Prev/Next bar; Share shows the "Link copied" toast; ingredient checkboxes strike through. Resize narrow to confirm the single-column layout. Note any visual gaps for follow-up.

---

## Self-Review

**Spec coverage:**
- Timestamped transcript → Task 1. ✓
- Prompt `start` + parse coercion → Task 2. ✓
- `Recipe.transcript` + migration + task wiring → Task 3. ✓
- `recipe_detail` steps/`_mmss`/credit-without-Video → Task 4. ✓
- Template (tap-to-seek, sync, cooking, share, checkboxes, Save reuse) + CSS → Task 5. ✓
- Graceful degradation (no video / null starts) → Task 4 + Task 5 tests. ✓
- Visual check → Task 6. ✓

**Placeholder scan:** none — all template/CSS/JS/test code is inline and complete.

**Type consistency:** `fetch_transcript -> str|None`; `_coerce_start -> int|None`; `_mmss(int|None) -> str`; context `steps` items `{number,text,start,start_display}` and `rv_data {"videoId", "steps":[int|None]}` are produced in Task 4 and consumed unchanged by the Task 5 template (`data.steps` → `starts`, `data.videoId` → `videoId`). Save partial uses `.rv-btn--fav/--secondary`, both defined in the Task 5 CSS.

**Notes / risks:**
- Migration `0003_recipe_transcript` collides in number with the unmerged cache branch's `0003_*`; reconcile with `makemigrations --merge` when both land (expected, not a blocker).
- The old detail page's inline Delete form is intentionally dropped (not in the design); the `delete_recipe` endpoint and its test are unaffected (deletion stays available from the Saved list).
