# Cookbook recipe-list view Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the plain `saved.html` with the Mise "Cookbook" view (design 1b: full-width grid + dropdown-facet toolbar), wired to real data via HTMX, backed by two new LLM-classified `Recipe` fields (`meal_type`, `dietary`).

**Architecture:** A shared pure-Python `recipes/facets.py` owns the meal/dietary vocabularies, normalizers, and querystring helpers. The `saved` view materializes the user's (small) cookbook, computes per-value facet counts, filters in Python (OR within a facet, AND across), sorts, and renders an HTMX-swappable fragment. Facet toggling is server-rendered (each option carries a precomputed "toggle this value" URL); Alpine only opens/closes dropdowns. The ML extractor classifies `meal_type`/`dietary` for new recipes; a management command backfills existing rows best-effort. `dietary` is stored but **not surfaced** in the UI this iteration.

**Tech Stack:** Django, HTMX, Alpine.js, pytest. ML service: FastAPI + httpx. Web venv `.venv-web`, ML venv `.venv-ml`.

## Global Constraints

- Web tests: `cd apps/web && ../../.venv-web/bin/pytest -q` (no `python` on PATH; use the venv).
- ML tests: `cd apps/audio-service && ../../.venv-ml/bin/pytest -q`.
- `MEAL_TYPES = ["breakfast", "lunch", "dinner", "dessert", "side", "snack"]` (single-value).
- `DIETARY_TAGS = ["vegetarian", "vegan", "gluten_free"]` (multi-value).
- Time buckets (non-overlapping, on `cook_time_minutes`): `under15` (≤15), `15-30` (>15,≤30), `30-60` (>30,≤60), `over60` (>60).
- Filter semantics: OR within one facet's selected values, AND across facets.
- Sorts: `recent` (default, newest first) · `quickest` (cook time asc, null cook time last).
- `dietary` is populated (extractor + backfill) but exposes **no filter facet and no card badge** this iteration.
- Routing unchanged: URL `/saved/`, url name `saved`. Existing default (no-`context`) `toggle_favorite` branch must keep returning `recipes/_recipe_card.html` (favorites page depends on it).
- Commit after every task. Each commit message ends with the `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.

---

### Task 1: `facets.py` — vocabulary, normalizers, querystring helpers

**Files:**
- Create: `apps/web/recipes/facets.py`
- Test: `apps/web/recipes/tests/test_facets.py`

**Interfaces:**
- Produces:
  - `MEAL_TYPES: list[str]`, `DIETARY_TAGS: list[str]`
  - `MEAL_LABELS: dict[str,str]`, `DIET_LABELS: dict[str,str]`
  - `TIME_BUCKETS: list[dict]` each `{"key","label","lo","hi"}`; `TIME_BUCKET_KEYS: list[str]`
  - `normalize_meal_type(value) -> str`
  - `normalize_dietary(value) -> list[str]`
  - `time_bucket(minutes: int | None) -> str | None`
  - `toggle_param(params, key, value) -> str` (multi-value toggle, returns urlencoded QS)
  - `set_param(params, key, value) -> str` (single-value set/replace)
  - `clear_filters(params, keep=("q","sort","view")) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# apps/web/recipes/tests/test_facets.py
from django.http import QueryDict

from recipes import facets


def test_normalize_meal_type_known_and_unknown():
    assert facets.normalize_meal_type("Dinner") == "dinner"
    assert facets.normalize_meal_type("  DESSERT ") == "dessert"
    assert facets.normalize_meal_type("brunch") == ""
    assert facets.normalize_meal_type(5) == ""


def test_normalize_dietary_filters_dedupes_and_coerces():
    assert facets.normalize_dietary(["Vegan", "bogus", "vegetarian"]) == ["vegan", "vegetarian"]
    assert facets.normalize_dietary("gluten-free") == ["gluten_free"]
    assert facets.normalize_dietary("Gluten Free") == ["gluten_free"]
    assert facets.normalize_dietary(["vegan", "vegan"]) == ["vegan"]
    assert facets.normalize_dietary(None) == []
    assert facets.normalize_dietary([1, "vegan"]) == ["vegan"]


def test_time_bucket_boundaries():
    assert facets.time_bucket(None) is None
    assert facets.time_bucket(15) == "under15"
    assert facets.time_bucket(16) == "15-30"
    assert facets.time_bucket(30) == "15-30"
    assert facets.time_bucket(60) == "30-60"
    assert facets.time_bucket(61) == "over60"


def test_toggle_param_adds_and_removes_preserving_others():
    q = QueryDict("cuisine=italian&meal=dinner")
    added = QueryDict(facets.toggle_param(q, "cuisine", "french"))
    assert added.getlist("cuisine") == ["italian", "french"]
    assert added.get("meal") == "dinner"
    removed = QueryDict(facets.toggle_param(q, "cuisine", "italian"))
    assert removed.getlist("cuisine") == []
    assert removed.get("meal") == "dinner"


def test_set_param_replaces_single_value():
    q = QueryDict("sort=recent&cuisine=italian")
    out = QueryDict(facets.set_param(q, "sort", "quickest"))
    assert out.get("sort") == "quickest"
    assert out.get("cuisine") == "italian"


def test_clear_filters_keeps_only_view_sort_q():
    q = QueryDict("q=soup&sort=quickest&view=list&cuisine=italian&meal=dinner")
    out = QueryDict(facets.clear_filters(q))
    assert out.get("q") == "soup"
    assert out.get("sort") == "quickest"
    assert out.get("view") == "list"
    assert "cuisine" not in out
    assert "meal" not in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_facets.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'recipes.facets'`.

- [ ] **Step 3: Write the implementation**

```python
# apps/web/recipes/facets.py
"""Cookbook facet vocabulary, normalization, and querystring helpers.

Single source of truth for the saved-recipe meal-type / dietary vocabularies
and the time-to-cook buckets. Imported by the Recipe model (choices), the
extraction mapping (tasks.py), the backfill command, and the cookbook view.
Pure Python + Django QueryDict — no ORM, no model imports (avoids a circular
import with models).
"""
from urllib.parse import urlencode

MEAL_TYPES = ["breakfast", "lunch", "dinner", "dessert", "side", "snack"]
DIETARY_TAGS = ["vegetarian", "vegan", "gluten_free"]

MEAL_LABELS = {
    "breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner",
    "dessert": "Dessert", "side": "Side", "snack": "Snack",
}
DIET_LABELS = {
    "vegetarian": "Vegetarian", "vegan": "Vegan", "gluten_free": "Gluten-free",
}

# Ordered, non-overlapping cook-time buckets. lo is exclusive, hi inclusive;
# None means unbounded on that side.
TIME_BUCKETS = [
    {"key": "under15", "label": "Under 15", "lo": None, "hi": 15},
    {"key": "15-30", "label": "15–30", "lo": 15, "hi": 30},
    {"key": "30-60", "label": "30–60", "lo": 30, "hi": 60},
    {"key": "over60", "label": "Over 60", "lo": 60, "hi": None},
]
TIME_BUCKET_KEYS = [b["key"] for b in TIME_BUCKETS]


def normalize_meal_type(value):
    """Lowercase/strip a meal type, returning it only if known, else ""."""
    if not isinstance(value, str):
        return ""
    v = value.strip().lower()
    return v if v in MEAL_TYPES else ""


def normalize_dietary(value):
    """Coerce to a deduped, ordered list of known dietary tags.

    Accepts a list/tuple or a single string; lowercases, maps spaces/hyphens to
    underscores, and drops blanks and unknown values.
    """
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for item in value:
        if not isinstance(item, str):
            continue
        v = item.strip().lower().replace("-", "_").replace(" ", "_")
        if v in DIETARY_TAGS and v not in out:
            out.append(v)
    return out


def time_bucket(minutes):
    """Return the bucket key for a cook time in minutes, or None if unknown."""
    if minutes is None:
        return None
    for b in TIME_BUCKETS:
        lo, hi = b["lo"], b["hi"]
        if (lo is None or minutes > lo) and (hi is None or minutes <= hi):
            return b["key"]
    return None


def _as_lists(params):
    """Normalize a QueryDict (or dict-of-lists) to a plain {key: [values]} dict."""
    if hasattr(params, "getlist"):
        return {k: params.getlist(k) for k in params}
    return {k: list(v) for k, v in params.items()}


def _encode(data):
    pairs = []
    for k, vals in data.items():
        for v in vals:
            if v != "":
                pairs.append((k, v))
    return urlencode(pairs)


def toggle_param(params, key, value):
    """Querystring with `value` toggled within multi-value `key`; others kept."""
    data = _as_lists(params)
    current = data.get(key, [])
    if value in current:
        current = [v for v in current if v != value]
    else:
        current = current + [value]
    data[key] = current
    return _encode(data)


def set_param(params, key, value):
    """Querystring with single-value `key` set to `value` (or cleared if empty)."""
    data = _as_lists(params)
    data[key] = [value] if value not in (None, "") else []
    return _encode(data)


def clear_filters(params, keep=("q", "sort", "view")):
    """Querystring keeping only the `keep` params (drops every active filter)."""
    data = {k: v for k, v in _as_lists(params).items() if k in keep}
    return _encode(data)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_facets.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/web/recipes/facets.py apps/web/recipes/tests/test_facets.py
git commit -m "feat(recipes): facet vocabulary, normalizers, and querystring helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `Recipe.meal_type` / `Recipe.dietary` fields + migration

**Files:**
- Modify: `apps/web/recipes/models.py` (Recipe, near `cuisine`)
- Create: `apps/web/recipes/migrations/0005_recipe_meal_type_dietary.py` (via makemigrations)
- Test: `apps/web/recipes/tests/test_models.py` (append)

**Interfaces:**
- Consumes: `recipes.facets.MEAL_TYPES`, `facets.MEAL_LABELS` (Task 1).
- Produces: `Recipe.meal_type: str` (choices), `Recipe.dietary: list[str]` (JSON, default `[]`).

- [ ] **Step 1: Write the failing test**

```python
# apps/web/recipes/tests/test_models.py  (append)
from recipes.models import Recipe


def test_recipe_meal_type_and_dietary_defaults(db, django_user_model):
    user = django_user_model.objects.create_user(email="m@e.com", password="supersecret")
    r = Recipe.objects.create(owner=user, title="X", meal_type="dinner", dietary=["vegan"])
    r.refresh_from_db()
    assert r.meal_type == "dinner"
    assert r.dietary == ["vegan"]
    blank = Recipe.objects.create(owner=user, title="Y")
    assert blank.meal_type == ""
    assert blank.dietary == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_models.py::test_recipe_meal_type_and_dietary_defaults -q`
Expected: FAIL — `TypeError`/`FieldError` (unknown field `meal_type`).

- [ ] **Step 3: Add the model fields**

In `apps/web/recipes/models.py`, add the import near the top:

```python
from . import facets
```

Then add these two fields inside `Recipe`, immediately after the `cuisine` field (line ~24):

```python
    meal_type = models.CharField(
        max_length=20, blank=True,
        choices=[(m, facets.MEAL_LABELS[m]) for m in facets.MEAL_TYPES],
    )
    dietary = models.JSONField(default=list)  # subset of facets.DIETARY_TAGS; not surfaced yet
```

- [ ] **Step 4: Generate the migration**

Run: `cd apps/web && ../../.venv-web/bin/python manage.py makemigrations recipes --name recipe_meal_type_dietary`
Expected: creates `recipes/migrations/0005_recipe_meal_type_dietary.py` adding both fields (the latest existing migration is `0004_recipe_transcript`).

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_models.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/recipes/models.py apps/web/recipes/migrations/0005_recipe_meal_type_dietary.py apps/web/recipes/tests/test_models.py
git commit -m "feat(recipes): add Recipe.meal_type and Recipe.dietary fields

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: ML extractor — classify `meal_type` / `dietary`

**Files:**
- Modify: `apps/audio-service/app/prompt.py`
- Modify: `apps/audio-service/app/extractor.py` (`parse_recipe_response` + module helpers)
- Test: `apps/audio-service/tests/test_extractor.py` (append)

**Interfaces:**
- Produces: `parse_recipe_response` now returns dicts with normalized `meal_type: str` and `dietary: list[str]`.
- Note: audio-service cannot import the web app; it keeps its own vocab copies.

- [ ] **Step 1: Write the failing tests**

```python
# apps/audio-service/tests/test_extractor.py  (append)
from app.extractor import parse_recipe_response


def test_parse_normalizes_meal_type_and_dietary():
    raw = '{"title": "T", "meal_type": "Dinner", "dietary": ["Vegan", "bogus"]}'
    out = parse_recipe_response(raw)
    assert out["meal_type"] == "dinner"
    assert out["dietary"] == ["vegan"]


def test_parse_defaults_meal_and_dietary_when_missing():
    out = parse_recipe_response('{"title": "T"}')
    assert out["meal_type"] == ""
    assert out["dietary"] == []


def test_parse_drops_unknown_meal_type():
    out = parse_recipe_response('{"title": "T", "meal_type": "brunch"}')
    assert out["meal_type"] == ""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps/audio-service && ../../.venv-ml/bin/pytest tests/test_extractor.py -q`
Expected: FAIL — `KeyError: 'meal_type'`.

- [ ] **Step 3: Add normalizers + wire into `parse_recipe_response`**

In `apps/audio-service/app/extractor.py`, add module-level constants and helpers above `parse_recipe_response`:

```python
_MEAL_TYPES = {"breakfast", "lunch", "dinner", "dessert", "side", "snack"}
_DIETARY = {"vegetarian", "vegan", "gluten_free"}


def _normalize_meal_type(value):
    if not isinstance(value, str):
        return ""
    v = value.strip().lower()
    return v if v in _MEAL_TYPES else ""


def _normalize_dietary(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for item in value:
        if not isinstance(item, str):
            continue
        v = item.strip().lower().replace("-", "_").replace(" ", "_")
        if v in _DIETARY and v not in out:
            out.append(v)
    return out
```

Then, inside `parse_recipe_response`, after the existing `recipe.setdefault("tags", [])` line, add:

```python
    recipe["meal_type"] = _normalize_meal_type(recipe.get("meal_type", ""))
    recipe["dietary"] = _normalize_dietary(recipe.get("dietary", []))
```

- [ ] **Step 4: Update the prompt**

In `apps/audio-service/app/prompt.py`, inside the JSON structure block, add these two keys after the `"tags"` line:

```
  "tags": ["relevant", "tags"],
  "meal_type": "one of: breakfast, lunch, dinner, dessert, side, snack (or \"\" if unclear)",
  "dietary": ["any of: vegetarian, vegan, gluten_free that clearly apply; [] if none"],
```

And add these bullets to the Guidelines list:

```
- "meal_type": the single best-fit meal category from the list above, or "" if unclear.
- "dietary": only tags clearly supported by the recipe. Use "vegan" only when no animal
  products at all; "vegetarian" when no meat or fish; "gluten_free" when no gluten
  ingredients. Use [] when none clearly apply.
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd apps/audio-service && ../../.venv-ml/bin/pytest tests/test_extractor.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/audio-service/app/prompt.py apps/audio-service/app/extractor.py apps/audio-service/tests/test_extractor.py
git commit -m "feat(ml): extract and normalize recipe meal_type and dietary

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Map `meal_type` / `dietary` onto saved recipes (`tasks.py`)

**Files:**
- Modify: `apps/web/recipes/tasks.py` (`run_extraction_job`, the `Recipe.objects.create(...)` call)
- Test: `apps/web/recipes/tests/test_tasks.py` (append)

**Interfaces:**
- Consumes: `facets.normalize_meal_type`, `facets.normalize_dietary` (Task 1); the ML summary dict (Task 3).

- [ ] **Step 1: Write the failing test**

```python
# apps/web/recipes/tests/test_tasks.py  (append)
from recipes import tasks
from recipes.models import ExtractionJob, Recipe


def test_run_extraction_job_maps_and_normalizes_facets(db, django_user_model, monkeypatch):
    user = django_user_model.objects.create_user(email="t@e.com", password="supersecret")
    job = ExtractionJob.objects.create(owner=user, source=ExtractionJob.Source.PASTE_TEXT)
    monkeypatch.setattr(tasks.ml_client, "extract", lambda transcript, title: {
        "title": "Soup", "meal_type": "Dinner", "dietary": ["Vegan", "bogus"],
    })
    tasks.run_extraction_job(job.id, transcript="some text")
    r = Recipe.objects.get(title="Soup")
    assert r.meal_type == "dinner"
    assert r.dietary == ["vegan"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_tasks.py::test_run_extraction_job_maps_and_normalizes_facets -q`
Expected: FAIL — created recipe has `meal_type == ""` / `dietary == []`.

- [ ] **Step 3: Wire the mapping**

In `apps/web/recipes/tasks.py`, add to the imports at the top:

```python
from . import facets
```

Then in the `Recipe.objects.create(...)` call, add two keyword arguments after `difficulty=...`:

```python
            difficulty=summary.get("difficulty", "") or "",
            meal_type=facets.normalize_meal_type(summary.get("meal_type", "")),
            dietary=facets.normalize_dietary(summary.get("dietary", [])),
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_tasks.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/recipes/tasks.py apps/web/recipes/tests/test_tasks.py
git commit -m "feat(recipes): persist normalized meal_type/dietary on extraction

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Backfill management command

**Files:**
- Create: `apps/web/recipes/management/commands/backfill_recipe_facets.py`
- Test: `apps/web/recipes/tests/test_backfill_facets.py`

**Interfaces:**
- Consumes: `Recipe` model; reads `tags` + `title`.
- Produces: management command `backfill_recipe_facets` with `--dry-run`.

- [ ] **Step 1: Write the failing tests**

```python
# apps/web/recipes/tests/test_backfill_facets.py
import pytest
from django.core.management import call_command

from recipes.models import Recipe


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(email="b@e.com", password="supersecret")


def test_backfill_derives_from_tags(user):
    r = Recipe.objects.create(owner=user, title="Pasta", tags=["Dinner", "Vegan"])
    call_command("backfill_recipe_facets")
    r.refresh_from_db()
    assert r.meal_type == "dinner"
    assert r.dietary == ["vegan"]


def test_backfill_does_not_overwrite_existing(user):
    r = Recipe.objects.create(owner=user, title="Cake", tags=["dessert"], meal_type="snack")
    call_command("backfill_recipe_facets")
    r.refresh_from_db()
    assert r.meal_type == "snack"  # untouched


def test_backfill_dry_run_writes_nothing(user):
    r = Recipe.objects.create(owner=user, title="Pasta", tags=["dinner"])
    call_command("backfill_recipe_facets", "--dry-run")
    r.refresh_from_db()
    assert r.meal_type == ""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_backfill_facets.py -q`
Expected: FAIL — `CommandError: Unknown command: 'backfill_recipe_facets'`.

- [ ] **Step 3: Write the command**

```python
# apps/web/recipes/management/commands/backfill_recipe_facets.py
"""Best-effort backfill of Recipe.meal_type / Recipe.dietary from tags + title.

Only fills empties (never overwrites). Heuristic keyword matching — values the
LLM didn't classify and whose tags/title give no signal are left blank.
"""
from django.core.management.base import BaseCommand

from recipes.models import Recipe

# First match wins (dict insertion order).
_MEAL_KEYWORDS = {
    "breakfast": "breakfast", "brunch": "breakfast",
    "dessert": "dessert", "cake": "dessert", "cookie": "dessert",
    "side": "side", "appetizer": "side",
    "snack": "snack",
    "lunch": "lunch",
    "dinner": "dinner", "supper": "dinner",
}
_DIET_KEYWORDS = {
    "vegan": "vegan",
    "vegetarian": "vegetarian", "veggie": "vegetarian",
    "gluten-free": "gluten_free", "gluten free": "gluten_free",
    "gluten_free": "gluten_free",
}


def _haystack(recipe):
    return (" ".join(str(t) for t in recipe.tags) + " " + recipe.title).lower()


def _derive_meal(recipe):
    hay = _haystack(recipe)
    for kw, meal in _MEAL_KEYWORDS.items():
        if kw in hay:
            return meal
    return ""


def _derive_diet(recipe):
    hay = _haystack(recipe)
    out = []
    for kw, diet in _DIET_KEYWORDS.items():
        if kw in hay and diet not in out:
            out.append(diet)
    return out


class Command(BaseCommand):
    help = "Backfill meal_type/dietary on recipes from tags + title (best effort)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report only.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        filled_meal = filled_diet = 0
        for recipe in Recipe.objects.all():
            changed = False
            if not recipe.meal_type:
                meal = _derive_meal(recipe)
                if meal:
                    recipe.meal_type = meal
                    filled_meal += 1
                    changed = True
            if not recipe.dietary:
                diet = _derive_diet(recipe)
                if diet:
                    recipe.dietary = diet
                    filled_diet += 1
                    changed = True
            if changed and not dry:
                recipe.save(update_fields=["meal_type", "dietary"])
        prefix = "[dry-run] " if dry else ""
        self.stdout.write(
            f"{prefix}filled meal_type on {filled_meal}, dietary on {filled_diet} recipes"
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_backfill_facets.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/web/recipes/management/commands/backfill_recipe_facets.py apps/web/recipes/tests/test_backfill_facets.py
git commit -m "feat(recipes): backfill_recipe_facets management command

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Cookbook view + grid templates (filter / sort / search / counts / empty states)

**Files:**
- Modify: `apps/web/recipes/views.py` (`saved`; `toggle_favorite` cookbook branch; add `Recipe.cook_time_display` via models)
- Modify: `apps/web/recipes/models.py` (add `cook_time_display` property)
- Create: `apps/web/templates/recipes/cookbook.html`
- Create: `apps/web/templates/recipes/_cookbook.html`
- Create: `apps/web/templates/recipes/_cookbook_card.html`
- Delete: `apps/web/templates/recipes/saved.html`
- Modify: `apps/web/templates/base.html` (add `.app-main--wide` opt-in block)
- Test: `apps/web/recipes/tests/test_cookbook.py`

**Interfaces:**
- Consumes: `facets.*` (Task 1); `Recipe.meal_type` (Task 2); existing `_annotated(qs, user)` in views.
- Produces:
  - `saved` returns context keys: `recipes`, `total`, `shown`, `q`, `sort`, `view`,
    `facet_groups` (`list[{name,label,options}]`, each option `{value,label,count,active,url}`),
    `fav_active`, `fav_count`, `fav_url`, `chips` (`list[{label,url}]`), `clear_url`,
    `has_filters`, `sort_options` (`list[{value,label,active,url}]`).
  - `toggle_favorite` returns `recipes/_cookbook_card.html` when POST `context == "cookbook"`.
  - `Recipe.cook_time_display -> str` (e.g. `"15 MIN"`, `"3 HR"`, `"1 HR 30 MIN"`, `""`).

- [ ] **Step 1: Write the failing tests**

```python
# apps/web/recipes/tests/test_cookbook.py
import pytest

from recipes.models import Favorite, Recipe


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(
        email="c@e.com", password="supersecret", onboarding_completed=True
    )


@pytest.fixture
def auth_client(client, user):
    client.login(username="c@e.com", password="supersecret")
    return client


def _mk(user, **kw):
    return Recipe.objects.create(owner=user, **kw)


def test_cookbook_renders_owner_recipes_with_swap_target(auth_client, user):
    _mk(user, title="Garlic Noodles")
    resp = auth_client.get("/saved/")
    assert resp.status_code == 200
    assert b"Garlic Noodles" in resp.content
    assert b'id="cookbook"' in resp.content


def test_cuisine_facet_filters(auth_client, user):
    _mk(user, title="Pasta", cuisine="italian")
    _mk(user, title="Sushi", cuisine="japanese")
    resp = auth_client.get("/saved/", {"cuisine": "italian"})
    assert b"Pasta" in resp.content
    assert b"Sushi" not in resp.content


def test_meal_facet_filters(auth_client, user):
    _mk(user, title="Eggs", meal_type="breakfast")
    _mk(user, title="Steak", meal_type="dinner")
    resp = auth_client.get("/saved/", {"meal": "breakfast"})
    assert b"Eggs" in resp.content
    assert b"Steak" not in resp.content


def test_time_bucket_filters(auth_client, user):
    _mk(user, title="Quick", cook_time_minutes=10)
    _mk(user, title="Slow", cook_time_minutes=120)
    resp = auth_client.get("/saved/", {"time": "under15"})
    assert b"Quick" in resp.content
    assert b"Slow" not in resp.content


def test_creator_facet_filters(auth_client, user):
    # NB: every creator name still appears in the creator dropdown (counts are
    # over the whole cookbook), so assert on unique recipe titles, not creators.
    _mk(user, title="KeepDish", channel_name="Lan's Kitchen")
    _mk(user, title="DropDish", channel_name="Preppy Kitchen")
    resp = auth_client.get("/saved/", {"creator": "Lan's Kitchen"})
    assert b"KeepDish" in resp.content
    assert b"DropDish" not in resp.content


def test_fav_filter(auth_client, user):
    r = _mk(user, title="Loved")
    _mk(user, title="Meh")
    Favorite.objects.create(user=user, recipe=r)
    resp = auth_client.get("/saved/", {"fav": "1"})
    assert b"Loved" in resp.content
    assert b"Meh" not in resp.content


def test_facets_are_anded_across_groups(auth_client, user):
    _mk(user, title="ItalDin", cuisine="italian", meal_type="dinner")
    _mk(user, title="ItalBrk", cuisine="italian", meal_type="breakfast")
    resp = auth_client.get("/saved/", {"cuisine": "italian", "meal": "dinner"})
    assert b"ItalDin" in resp.content
    assert b"ItalBrk" not in resp.content


def test_multiselect_within_group_is_or(auth_client, user):
    # Titles chosen so none is a substring of a cuisine value shown in the dropdown.
    _mk(user, title="DishOne", cuisine="italian")
    _mk(user, title="DishTwo", cuisine="japanese")
    _mk(user, title="DishThree", cuisine="french")
    resp = auth_client.get("/saved/", {"cuisine": ["italian", "japanese"]})
    assert b"DishOne" in resp.content and b"DishTwo" in resp.content
    assert b"DishThree" not in resp.content


def test_sort_quickest_orders_by_cook_time_nulls_last(auth_client, user):
    _mk(user, title="Slow", cook_time_minutes=90)
    _mk(user, title="Fast", cook_time_minutes=10)
    _mk(user, title="Unknown", cook_time_minutes=None)
    resp = auth_client.get("/saved/", {"sort": "quickest"})
    body = resp.content.decode()
    assert body.index("Fast") < body.index("Slow") < body.index("Unknown")


def test_search_matches_title_and_creator(auth_client, user):
    _mk(user, title="Tomato Soup")
    _mk(user, title="Pancakes", channel_name="Soupy Channel")
    _mk(user, title="Salad")
    resp = auth_client.get("/saved/", {"q": "soup"})
    assert b"Tomato Soup" in resp.content
    assert b"Pancakes" in resp.content
    assert b"Salad" not in resp.content


def test_empty_cold_state_when_no_recipes(auth_client, user):
    resp = auth_client.get("/saved/")
    assert b"Nothing saved yet" in resp.content


def test_empty_filtered_state_when_no_match(auth_client, user):
    _mk(user, title="Pasta", cuisine="italian")
    resp = auth_client.get("/saved/", {"cuisine": "thai"})
    assert b"Nothing matches" in resp.content


def test_fav_toggle_cookbook_context_returns_card(auth_client, user):
    r = _mk(user, title="Pasta")
    resp = auth_client.post(f"/recipes/{r.id}/favorite/", {"context": "cookbook"})
    assert f'id="recipe-{r.id}"'.encode() in resp.content
    assert b"fav on" in resp.content  # now favorited


def test_cook_time_display():
    assert Recipe(cook_time_minutes=15).cook_time_display == "15 MIN"
    assert Recipe(cook_time_minutes=180).cook_time_display == "3 HR"
    assert Recipe(cook_time_minutes=90).cook_time_display == "1 HR 30 MIN"
    assert Recipe(cook_time_minutes=None).cook_time_display == ""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_cookbook.py -q`
Expected: FAIL — `TemplateDoesNotExist: recipes/cookbook.html` / missing `cook_time_display`.

- [ ] **Step 3: Add the `cook_time_display` property**

In `apps/web/recipes/models.py`, add this property to `Recipe` (after `__str__`):

```python
    @property
    def cook_time_display(self):
        m = self.cook_time_minutes
        if not m:
            return ""
        if m % 60 == 0:
            return f"{m // 60} HR" if m >= 60 else f"{m} MIN"
        if m > 60:
            return f"{m // 60} HR {m % 60} MIN"
        return f"{m} MIN"
```

- [ ] **Step 4: Rewrite the `saved` view + cookbook `toggle_favorite` branch**

In `apps/web/recipes/views.py`, add to the imports:

```python
from collections import Counter

from . import facets
```

Replace the existing `saved` view with:

```python
SORTS = {"recent": "Recently added", "quickest": "Quickest first"}


def _facet_group(name, label, params, sel, counts, *, order=None, labels=None):
    keys = order if order is not None else sorted(counts, key=lambda k: (-counts[k], k))
    options = []
    for value in keys:
        count = counts.get(value, 0)
        if count == 0:
            continue
        options.append({
            "value": value,
            "label": labels[value] if labels else value,
            "count": count,
            "active": value in sel,
            "url": facets.toggle_param(params, name, value),
        })
    return {"name": name, "label": label, "options": options}


@login_required
@onboarding_required
def saved(request):
    user = request.user
    params = request.GET
    cookbook = list(_annotated(Recipe.objects.filter(owner=user), user))
    total = len(cookbook)

    q = params.get("q", "").strip()
    sel = {
        "cuisine": params.getlist("cuisine"),
        "meal": params.getlist("meal"),
        "time": [t for t in params.getlist("time") if t in facets.TIME_BUCKET_KEYS],
        "creator": params.getlist("creator"),
    }
    fav = params.get("fav") == "1"
    sort = params.get("sort") if params.get("sort") in SORTS else "recent"
    view = "list" if params.get("view") == "list" else "grid"

    # Per-value counts over the whole cookbook (documented simplification).
    cuisine_counts = Counter(r.cuisine for r in cookbook if r.cuisine)
    creator_counts = Counter(r.channel_name for r in cookbook if r.channel_name)
    meal_counts = Counter(r.meal_type for r in cookbook if r.meal_type)
    time_counts = Counter(
        b for r in cookbook if (b := facets.time_bucket(r.cook_time_minutes))
    )
    fav_count = sum(1 for r in cookbook if r.is_favorite)

    ql = q.lower()

    def keep(r):
        if ql and ql not in r.title.lower() and ql not in (r.channel_name or "").lower():
            return False
        if sel["cuisine"] and r.cuisine not in sel["cuisine"]:
            return False
        if sel["meal"] and r.meal_type not in sel["meal"]:
            return False
        if sel["time"] and facets.time_bucket(r.cook_time_minutes) not in sel["time"]:
            return False
        if sel["creator"] and r.channel_name not in sel["creator"]:
            return False
        if fav and not r.is_favorite:
            return False
        return True

    results = [r for r in cookbook if keep(r)]
    if sort == "quickest":
        results.sort(key=lambda r: (r.cook_time_minutes is None, r.cook_time_minutes or 0))
    else:
        results.sort(key=lambda r: r.created_at, reverse=True)

    facet_groups = [
        _facet_group("cuisine", "Cuisine", params, sel["cuisine"], cuisine_counts),
        _facet_group("meal", "Meal type", params, sel["meal"], meal_counts,
                     order=facets.MEAL_TYPES, labels=facets.MEAL_LABELS),
        _facet_group("time", "Time", params, sel["time"], time_counts,
                     order=facets.TIME_BUCKET_KEYS,
                     labels={b["key"]: b["label"] for b in facets.TIME_BUCKETS}),
        _facet_group("creator", "Creator", params, sel["creator"], creator_counts),
    ]

    chips = []
    for group in facet_groups:
        for opt in group["options"]:
            if opt["active"]:
                chips.append({"label": opt["label"], "url": opt["url"]})
    if fav:
        chips.append({"label": "Favorites", "url": facets.toggle_param(params, "fav", "1")})

    sort_options = [
        {"value": key, "label": label, "active": key == sort,
         "url": facets.set_param(params, "sort", key)}
        for key, label in SORTS.items()
    ]

    return render(request, "recipes/cookbook.html", {
        "recipes": results,
        "total": total,
        "shown": len(results),
        "q": q,
        "sort": sort,
        "sort_label": SORTS[sort],
        "sort_options": sort_options,
        "view": view,
        "grid_url": facets.set_param(params, "view", "grid"),
        "list_url": facets.set_param(params, "view", "list"),
        "facet_groups": facet_groups,
        "fav_active": fav,
        "fav_count": fav_count,
        "fav_url": facets.toggle_param(params, "fav", "1"),
        "chips": chips,
        "clear_url": facets.clear_filters(params),
        "has_filters": bool(q or fav or any(sel.values())),
    })
```

Then in `toggle_favorite`, add a branch before the final `else`:

```python
    elif request.POST.get("context") == "cookbook":
        template = "recipes/_cookbook_card.html"
```

- [ ] **Step 5: Add the `.app-main--wide` modifier**

In `apps/web/templates/base.html`, replace the `<main>` line with one that honors an optional block:

```html
  <main class="app-main {% block main_class %}{% endblock %}">{% block content %}{% endblock %}</main>
```

And in `apps/web/static/css/components.css` (top of file is fine) add:

```css
.app-main--wide { max-width: 1180px; }
```

- [ ] **Step 6: Create `cookbook.html`**

```html
{% extends "base.html" %}
{% block title %}Saved{% endblock %}
{% block main_class %}app-main--wide{% endblock %}
{% block content %}
<div class="cookbook" id="cookbook">
  {% include "recipes/_cookbook.html" %}
</div>
{% endblock %}
```

- [ ] **Step 7: Create `_cookbook.html` (toolbar + chips + grid + empty states)**

```html
{% load static %}
<div class="mhead">
  <div>
    <div class="count">{% if has_filters %}{{ shown }} OF {{ total }} RECIPES{% else %}{{ total }} RECIPE{{ total|pluralize }} IN YOUR COOKBOOK{% endif %}</div>
    <h3 class="htitle" style="font-size:27px;">Your cookbook</h3>
  </div>
  <div style="display:flex; align-items:center; gap:12px;" x-data="{ sortOpen: false }">
    <div style="position:relative;">
      <span class="sort" @click="sortOpen = !sortOpen" style="cursor:pointer;">{{ sort_label|upper }}
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"></path></svg></span>
      <div class="ddmenu" x-show="sortOpen" @click.outside="sortOpen = false" x-cloak style="right:0; width:180px;">
        {% for opt in sort_options %}
        <a class="mrow {% if opt.active %}on{% endif %}" href="?{{ opt.url }}"
           hx-get="?{{ opt.url }}" hx-target="#cookbook" hx-select="#cookbook" hx-swap="innerHTML" hx-push-url="true">{{ opt.label }}</a>
        {% endfor %}
      </div>
    </div>
    <div class="vtog">
      <a class="{% if view == 'grid' %}on{% endif %}" href="?{{ grid_url }}" hx-get="?{{ grid_url }}" hx-target="#cookbook" hx-select="#cookbook" hx-swap="innerHTML" hx-push-url="true" aria-label="Grid view">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><rect x="3" y="3" width="7" height="7" rx="1"></rect><rect x="14" y="3" width="7" height="7" rx="1"></rect><rect x="3" y="14" width="7" height="7" rx="1"></rect><rect x="14" y="14" width="7" height="7" rx="1"></rect></svg></a>
      <a class="{% if view == 'list' %}on{% endif %}" href="?{{ list_url }}" hx-get="?{{ list_url }}" hx-target="#cookbook" hx-select="#cookbook" hx-swap="innerHTML" hx-push-url="true" aria-label="List view">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3.5" y1="6" x2="3.51" y2="6"></line><line x1="3.5" y1="12" x2="3.51" y2="12"></line><line x1="3.5" y1="18" x2="3.51" y2="18"></line></svg></a>
    </div>
  </div>
</div>

<div class="toolbar" style="margin-bottom:18px;">
  {% for group in facet_groups %}
  <div style="position:relative;" x-data="{ open: false }">
    <span class="ddbtn {% if group.name in '' %}{% endif %}" @click="open = !open" style="cursor:pointer;">{{ group.label }}
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"></path></svg></span>
    <div class="ddmenu" x-show="open" @click.outside="open = false" x-cloak>
      <div class="mlabel">{{ group.label|upper }} · MULTI-SELECT</div>
      {% for opt in group.options %}
      <a class="mrow {% if opt.active %}on{% endif %}" href="?{{ opt.url }}"
         hx-get="?{{ opt.url }}" hx-target="#cookbook" hx-select="#cookbook" hx-swap="innerHTML" hx-push-url="true">
        <span class="cbox">{% if opt.active %}<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg>{% endif %}</span>
        {{ opt.label }}<span class="ct">{{ opt.count }}</span></a>
      {% endfor %}
    </div>
  </div>
  {% endfor %}
  <a class="ddbtn {% if fav_active %}on{% endif %}" href="?{{ fav_url }}" hx-get="?{{ fav_url }}" hx-target="#cookbook" hx-select="#cookbook" hx-swap="innerHTML" hx-push-url="true">Favorites{% if fav_count %} <span class="ct">{{ fav_count }}</span>{% endif %}</a>
</div>

{% if chips %}
<div class="achips" style="padding-bottom:18px; margin-bottom:6px; border-bottom:1px solid var(--line);">
  {% for chip in chips %}
  <a class="achip" href="?{{ chip.url }}" hx-get="?{{ chip.url }}" hx-target="#cookbook" hx-select="#cookbook" hx-swap="innerHTML" hx-push-url="true">{{ chip.label }}<span class="x"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"></path></svg></span></a>
  {% endfor %}
  <a class="clearall" href="?{{ clear_url }}" hx-get="?{{ clear_url }}" hx-target="#cookbook" hx-select="#cookbook" hx-swap="innerHTML" hx-push-url="true">Clear all</a>
</div>
{% endif %}

{% if recipes %}
  <div class="grid3">
    {% for recipe in recipes %}{% include "recipes/_cookbook_card.html" %}{% endfor %}
  </div>
{% elif has_filters %}
  <div class="empty">
    <div class="eicon"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"></circle><path d="m21 21-4.3-4.3"></path></svg></div>
    <h3 class="htitle" style="font-size:24px;">Nothing matches</h3>
    <p style="color:var(--ink-2); margin:8px 0 20px;">No saved recipes fit those filters.</p>
    <a class="ebtn ghost" href="?{{ clear_url }}" hx-get="?{{ clear_url }}" hx-target="#cookbook" hx-select="#cookbook" hx-swap="innerHTML" hx-push-url="true">Clear all filters</a>
  </div>
{% else %}
  <div class="empty">
    <div class="eicon"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg></div>
    <h3 class="htitle" style="font-size:24px;">Nothing saved yet</h3>
    <p style="color:var(--ink-2); margin:8px 0 20px;">Recipes you save from Discover land in your cookbook.</p>
    <a class="ebtn" href="{% url 'discover' %}">Discover recipes</a>
  </div>
{% endif %}
```

- [ ] **Step 8: Create `_cookbook_card.html` (grid card)**

```html
{% load static %}
<div class="rcard" id="recipe-{{ recipe.id }}">
  <div class="rthumb" style="background:linear-gradient(150deg, var(--surface-2), color-mix(in srgb, var(--secondary) 18%, var(--surface-2)));">
    {% if recipe.thumbnail_url %}<img src="{{ recipe.thumbnail_url }}" alt="" style="position:absolute; inset:0; width:100%; height:100%; object-fit:cover;">{% endif %}
    <span class="play"><svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 4 20 12 6 20"></polygon></svg></span>
    <form hx-post="{% url 'toggle_favorite' recipe.id %}" hx-target="#recipe-{{ recipe.id }}" hx-swap="outerHTML" style="position:absolute; right:10px; top:10px; margin:0;">
      {% csrf_token %}
      <input type="hidden" name="context" value="cookbook">
      <input type="hidden" name="view" value="{{ view }}">
      <button type="submit" class="fav {% if recipe.is_favorite %}on{% endif %}" aria-label="{% if recipe.is_favorite %}Remove from favorites{% else %}Add to favorites{% endif %}">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="{% if recipe.is_favorite %}currentColor{% else %}none{% endif %}" stroke="currentColor" stroke-width="1.6"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
      </button>
    </form>
  </div>
  <div style="padding:15px 16px 17px;">
    <div class="ceyebrow">{% if recipe.cuisine %}{{ recipe.cuisine|upper }}{% endif %}{% if recipe.cuisine and recipe.meal_type %} · {% endif %}{% if recipe.meal_type %}{{ recipe.get_meal_type_display|upper }}{% endif %}</div>
    <h4 class="rtitle"><a href="{% url 'recipe_detail' recipe.id %}" style="color:inherit;">{{ recipe.title }}</a></h4>
    {% if recipe.channel_name %}<div class="credit"><span class="av"></span><span class="cn">{{ recipe.channel_name }}</span></div>{% endif %}
    <div class="cfoot">
      {% if recipe.cook_time_display %}<span class="badge">{{ recipe.cook_time_display }}</span>{% endif %}
      {% if recipe.difficulty %}<span class="badge">{{ recipe.difficulty|upper }}</span>{% endif %}
    </div>
  </div>
</div>
```

- [ ] **Step 9: Delete the old template**

```bash
git rm apps/web/templates/recipes/saved.html
```

- [ ] **Step 10: Run the tests to verify they pass**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_cookbook.py recipes/tests/test_pages.py -q`
Expected: PASS (new cookbook tests + the existing `test_saved_*` / favorite tests still green).

- [ ] **Step 11: Commit**

```bash
git add apps/web/recipes/views.py apps/web/recipes/models.py apps/web/templates/recipes/cookbook.html apps/web/templates/recipes/_cookbook.html apps/web/templates/recipes/_cookbook_card.html apps/web/templates/base.html apps/web/static/css/components.css apps/web/recipes/tests/test_cookbook.py
git rm apps/web/templates/recipes/saved.html
git commit -m "feat(recipes): Cookbook grid view with server-rendered facet filters

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: List view + favorite-toggle row variant

**Files:**
- Modify: `apps/web/recipes/views.py` (`toggle_favorite` cookbook branch → row when `view=list`)
- Modify: `apps/web/templates/recipes/_cookbook.html` (list branch)
- Create: `apps/web/templates/recipes/_cookbook_row.html`
- Test: `apps/web/recipes/tests/test_cookbook.py` (append)

**Interfaces:**
- Consumes: context from Task 6 (`view`, `recipes`).
- Produces: `toggle_favorite` returns `recipes/_cookbook_row.html` when POST `context == "cookbook"` and `view == "list"`.

- [ ] **Step 1: Write the failing tests**

```python
# apps/web/recipes/tests/test_cookbook.py  (append)
def test_list_view_renders_rows_with_description(auth_client, user):
    _mk(user, title="Garlic Noodles", description="Silky buttered noodles.")
    resp = auth_client.get("/saved/", {"view": "list"})
    assert b"lrow" in resp.content
    assert b"Silky buttered noodles." in resp.content


def test_fav_toggle_in_list_view_returns_row(auth_client, user):
    r = _mk(user, title="Pasta")
    resp = auth_client.post(
        f"/recipes/{r.id}/favorite/", {"context": "cookbook", "view": "list"}
    )
    assert b"lrow" in resp.content
    assert f'id="recipe-{r.id}"'.encode() in resp.content
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_cookbook.py -q -k "list"`
Expected: FAIL — no `lrow` markup (grid renders instead).

- [ ] **Step 3: Add the list branch to `_cookbook.html`**

In `apps/web/templates/recipes/_cookbook.html`, replace the grid `{% if recipes %}` block's first branch with a view switch:

```html
{% if recipes %}
  {% if view == 'list' %}
  <div>
    {% for recipe in recipes %}{% include "recipes/_cookbook_row.html" %}{% endfor %}
  </div>
  {% else %}
  <div class="grid3">
    {% for recipe in recipes %}{% include "recipes/_cookbook_card.html" %}{% endfor %}
  </div>
  {% endif %}
{% elif has_filters %}
```

(Leave the `{% elif has_filters %}` / `{% else %}` empty-state branches unchanged.)

- [ ] **Step 4: Create `_cookbook_row.html`**

```html
{% load static %}
<div class="lrow" id="recipe-{{ recipe.id }}">
  <div class="lthumb" style="background:linear-gradient(150deg, var(--surface-2), color-mix(in srgb, var(--secondary) 18%, var(--surface-2)));">
    {% if recipe.thumbnail_url %}<img src="{{ recipe.thumbnail_url }}" alt="" style="position:absolute; inset:0; width:100%; height:100%; object-fit:cover;">{% endif %}
    <span class="play"><svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 4 20 12 6 20"></polygon></svg></span>
  </div>
  <div style="flex:1; display:flex; flex-direction:column;">
    <div class="ceyebrow">{% if recipe.cuisine %}{{ recipe.cuisine|upper }}{% endif %}{% if recipe.cuisine and recipe.meal_type %} · {% endif %}{% if recipe.meal_type %}{{ recipe.get_meal_type_display|upper }}{% endif %}</div>
    <h4 class="ltitle"><a href="{% url 'recipe_detail' recipe.id %}" style="color:inherit;">{{ recipe.title }}</a></h4>
    {% if recipe.channel_name %}<div class="credit"><span class="av"></span><span class="cn">{{ recipe.channel_name }}</span></div>{% endif %}
    {% if recipe.description %}<p style="font-size:13px; color:var(--ink-2); line-height:1.5; margin:0 0 12px; max-width:480px;">{{ recipe.description }}</p>{% endif %}
    <div style="margin-top:auto; display:flex; align-items:center; gap:8px;">
      {% if recipe.cook_time_display %}<span class="badge">{{ recipe.cook_time_display }}</span>{% endif %}
      {% if recipe.difficulty %}<span class="badge">{{ recipe.difficulty|upper }}</span>{% endif %}
      <span style="flex:1;"></span>
      <form hx-post="{% url 'toggle_favorite' recipe.id %}" hx-target="#recipe-{{ recipe.id }}" hx-swap="outerHTML" style="margin:0; display:inline-flex;">
        {% csrf_token %}
        <input type="hidden" name="context" value="cookbook">
        <input type="hidden" name="view" value="list">
        <button type="submit" class="fav {% if recipe.is_favorite %}on{% endif %}" style="position:static; box-shadow:none; background:none;" aria-label="{% if recipe.is_favorite %}Remove from favorites{% else %}Add to favorites{% endif %}">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="{% if recipe.is_favorite %}currentColor{% else %}none{% endif %}" stroke="currentColor" stroke-width="1.6"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
        </button>
      </form>
    </div>
  </div>
</div>
```

- [ ] **Step 5: Extend the `toggle_favorite` cookbook branch**

In `apps/web/recipes/views.py`, replace the cookbook branch added in Task 6 with:

```python
    elif request.POST.get("context") == "cookbook":
        if request.POST.get("view") == "list":
            template = "recipes/_cookbook_row.html"
        else:
            template = "recipes/_cookbook_card.html"
```

The `recipe` passed to the row template needs `is_favorite` (already set above) and renders fine without `view` in context (the row hardcodes `view=list`).

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd apps/web && ../../.venv-web/bin/pytest recipes/tests/test_cookbook.py -q`
Expected: PASS (all cookbook tests, grid + list).

- [ ] **Step 7: Commit**

```bash
git add apps/web/recipes/views.py apps/web/templates/recipes/_cookbook.html apps/web/templates/recipes/_cookbook_row.html apps/web/recipes/tests/test_cookbook.py
git commit -m "feat(recipes): Cookbook list view and row favorite toggle

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Port design CSS + visual verification

**Files:**
- Modify: `apps/web/static/css/components.css` (append the 1b component classes)
- Reference (read-only): the design `<style>` block saved at the get_file output path in the spec.

**Interfaces:**
- Consumes: design tokens already in `tokens.css` (same names).
- Produces: styled `.cookbook` view matching design 1b.

- [ ] **Step 1: Append the ported component CSS**

Append to `apps/web/static/css/components.css` the 1b classes (ported verbatim from the design `<style>`; tokens already match). Scope the colliding `.badge` under `.cookbook`:

```css
/* ---- cookbook (saved) view — design 1b ---- */
.cookbook .mhead { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
.cookbook .count { font-family: var(--font-mono); font-size: 11px; letter-spacing: .12em; color: var(--muted); margin-bottom: 7px; }
.cookbook .htitle { font-family: var(--font-display); font-weight: 400; letter-spacing: -.015em; color: var(--ink); margin: 0; }
.cookbook .sort { display: inline-flex; align-items: center; gap: 7px; padding: 8px 13px; border: 1px solid var(--line-2); border-radius: 999px; background: var(--surface); font-family: var(--font-mono); font-size: 11.5px; letter-spacing: .04em; color: var(--ink-2); }
.cookbook .vtog { display: flex; border: 1px solid var(--line-2); border-radius: 9px; overflow: hidden; background: var(--surface); }
.cookbook .vtog > a { width: 34px; height: 32px; display: flex; align-items: center; justify-content: center; color: var(--muted); }
.cookbook .vtog > a.on { background: var(--accent-soft); color: var(--accent); }
.cookbook .toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.cookbook .ddbtn { display: inline-flex; align-items: center; gap: 8px; padding: 8px 14px; border-radius: 999px; border: 1px solid var(--line-2); background: var(--surface); color: var(--ink-2); font-size: 13px; cursor: pointer; }
.cookbook .ddbtn.on { background: var(--accent-soft); border-color: var(--accent-line); color: var(--on-soft); font-weight: 600; }
.cookbook .ddbtn .ct { font-family: var(--font-mono); font-size: 10.5px; padding: 1px 7px; border-radius: 999px; background: var(--accent); color: var(--on-accent); }
.cookbook .achips { display: flex; align-items: center; flex-wrap: wrap; gap: 9px; }
.cookbook .achip { display: inline-flex; align-items: center; gap: 8px; padding: 6px 9px 6px 13px; border-radius: 999px; background: var(--accent-soft); border: 1px solid var(--accent-line); color: var(--on-soft); font-size: 12.5px; font-weight: 600; }
.cookbook .achip .x { width: 17px; height: 17px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: color-mix(in srgb, var(--accent) 22%, transparent); }
.cookbook .clearall { font-family: var(--font-mono); font-size: 11px; letter-spacing: .07em; text-transform: uppercase; color: var(--accent); }
.cookbook .ddmenu { position: absolute; z-index: 20; width: 244px; background: var(--surface); border: 1px solid var(--line-2); border-radius: 14px; box-shadow: var(--shadow-2); padding: 8px; margin-top: 6px; }
.cookbook .ddmenu .mlabel { font-family: var(--font-mono); font-size: 10px; letter-spacing: .14em; color: var(--muted); padding: 8px 10px 6px; }
.cookbook .mrow { display: flex; align-items: center; gap: 11px; padding: 9px 10px; border-radius: 9px; font-size: 14px; color: var(--ink-2); }
.cookbook .mrow.on { color: var(--ink); font-weight: 600; }
.cookbook .mrow .cbox { width: 18px; height: 18px; border-radius: 5px; border: 1.5px solid var(--line-2); background: var(--surface); flex: 0 0 auto; display: flex; align-items: center; justify-content: center; color: transparent; }
.cookbook .mrow.on .cbox { background: var(--accent); border-color: var(--accent); color: var(--on-accent); }
.cookbook .mrow .ct { margin-left: auto; font-family: var(--font-mono); font-size: 11px; color: var(--muted); }
.cookbook .grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.cookbook .rcard { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; box-shadow: var(--shadow-1); display: flex; flex-direction: column; }
.cookbook .rthumb { position: relative; aspect-ratio: 16/10; }
.cookbook .play { position: absolute; left: 10px; bottom: 10px; width: 30px; height: 30px; border-radius: 50%; background: color-mix(in srgb, var(--paper) 82%, transparent); backdrop-filter: blur(6px); display: flex; align-items: center; justify-content: center; color: var(--accent); box-shadow: var(--shadow-1); }
.cookbook .fav { border: none; cursor: pointer; width: 34px; height: 34px; border-radius: 50%; background: color-mix(in srgb, var(--paper) 84%, transparent); backdrop-filter: blur(6px); display: flex; align-items: center; justify-content: center; color: var(--muted); box-shadow: var(--shadow-1); }
.cookbook .fav.on { color: var(--secondary); }
.cookbook .ceyebrow { font-family: var(--font-mono); font-size: 10px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
.cookbook .rtitle { font-family: var(--font-display); font-weight: 500; font-size: 19px; line-height: 1.16; margin: 0 0 9px; color: var(--ink); }
.cookbook .credit { display: flex; align-items: center; gap: 8px; margin-bottom: 13px; }
.cookbook .credit .av { width: 21px; height: 21px; border-radius: 50%; background: var(--secondary-soft); border: 1px solid var(--line); }
.cookbook .credit .cn { font-size: 13px; color: var(--ink-2); }
.cookbook .cfoot { display: flex; align-items: center; gap: 6px; }
.cookbook .badge { font-family: var(--font-mono); font-size: 11px; letter-spacing: .03em; padding: 4px 9px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); color: var(--ink-2); }
.cookbook .lrow { display: flex; gap: 20px; padding: 18px 0; border-bottom: 1px solid var(--line); }
.cookbook .lthumb { position: relative; width: 220px; flex: 0 0 auto; aspect-ratio: 16/10; border-radius: 12px; overflow: hidden; }
.cookbook .ltitle { font-family: var(--font-display); font-weight: 500; font-size: 21px; line-height: 1.12; margin: 0 0 9px; color: var(--ink); }
.cookbook .empty { padding: 76px 40px 60px; display: flex; flex-direction: column; align-items: center; text-align: center; }
.cookbook .eicon { width: 70px; height: 70px; border-radius: 50%; background: var(--accent-soft); color: var(--accent); display: flex; align-items: center; justify-content: center; margin-bottom: 22px; }
.cookbook .ebtn { display: inline-flex; align-items: center; gap: 8px; padding: 11px 20px; border-radius: 999px; background: var(--accent); color: var(--on-accent); font-size: 14px; font-weight: 600; box-shadow: var(--shadow-1); }
.cookbook .ebtn.ghost { background: var(--surface); border: 1px solid var(--line-2); color: var(--ink); box-shadow: none; }
[x-cloak] { display: none !important; }
```

- [ ] **Step 2: Verify CSS does not break existing tests**

Run: `cd apps/web && ../../.venv-web/bin/pytest -q`
Expected: PASS (full web suite — static rendering unaffected).

- [ ] **Step 3: Visual check via the running-web-app skill**

Use the `running-web-app` skill (apps/web) to launch the app and screenshot `/saved/` for a user with several saved recipes spanning cuisines / meal types / cook times. Confirm: 3-col grid, dropdown facets open/close, active chips + Clear all, grid↔list toggle, both empty states. Note any visual gaps vs design 1b and fix in CSS only.

- [ ] **Step 4: Commit**

```bash
git add apps/web/static/css/components.css
git commit -m "style(recipes): port Cookbook 1b component styles

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review notes

- **Spec coverage:** §A→T2; §B→T3; §C→T4; §D→T5; §E→T6 (filters/sort/search/counts/facet URLs); §F→T6+T7 (templates, empty states, fav toggle); §G→T8; §H→T1/T3/T5/T6/T7 tests. Dietary "collected not surfaced": fields populated (T2–T5), no facet/badge in templates (T6/T7) — verified by `test_*` asserting no diet UI implicitly (no dietary query param handled).
- **Simplifications carried from spec:** facet counts over whole cookbook (T6 `_facet_group`); fav-count refresh deferred (T6/T7 swap single card).
- **Type consistency:** `facets.toggle_param/set_param/clear_filters/time_bucket/normalize_*` names identical across T1/T4/T6. `cook_time_display` defined T6, used T6/T7. `context == "cookbook"` branch consistent T6→T7.
