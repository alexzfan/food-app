# Cookbook recipe-list view — design

**Date:** 2026-06-29
**Branch:** `feat/cookbook-recipe-list-view`
**Design source:** Claude Design project `08c47bb6-766a-4a23-b6e5-6e3899349d3d`, file `mise/Cookbook.dc.html` (direction **1b — toolbar facets**).

## Goal

Replace the plain `recipes/saved.html` with the polished **Cookbook** view from the Mise
design system (1b: full-width grid + a compact dropdown-facet toolbar), wired to real data
with HTMX. The Cookbook is the user's saved-recipe library, filterable by multiple facets.

To reach full design fidelity, add two real `Recipe` fields — `meal_type` and `dietary` —
classified by the LLM extractor for new recipes and backfilled best-effort for existing rows.

Out of scope: the design's 1a filter-rail direction; the "Cooked recently" facet (no
backing data); the "Ingredient on hand" facet; the **dietary filter facet + card diet
badge** (data is collected but not surfaced yet — see §A). The existing standalone
Favorites page is left untouched (Favorites also appears as a quick-toggle inside the
Cookbook).

Routing stays as-is: URL `/saved/`, url name `saved`, nav label "Saved". The page heading
becomes "Your cookbook".

## A. Data model — `apps/web/recipes/models.py` (+ migration `0005`)

Add to `Recipe`:

- `meal_type` — `CharField(max_length=20, blank=True, choices=MealType.choices)`.
  New `MealType` TextChoices: `breakfast, lunch, dinner, dessert, side, snack`.
  Single value. Renders in card eyebrow as `CUISINE · MEAL`.
- `dietary` — `JSONField(default=list)`. Closed vocabulary: `vegetarian | vegan |
  gluten_free`. A recipe may carry several. **Stored but not surfaced in the UI yet**: the
  field is populated by the extractor + backfill so we accumulate data to audit LLM
  accuracy, but there is no dietary filter facet and no card diet badge in this iteration
  (dietary accuracy is higher-stakes than meal type — a wrong "vegan"/"gluten-free" is
  misleading). The filter + badge get added in a later iteration once accuracy is trusted.

Define the allowed vocabularies once as module constants reused by the extractor mapping,
the backfill command, and the view's facet lists:
- `MEAL_TYPES = [breakfast, lunch, dinner, dessert, side, snack]`
- `DIETARY_TAGS = [vegetarian, vegan, gluten_free]`

Display labels: title-cased, `gluten_free → "Gluten-free"`, badge `GF`.

Migration `0005_recipe_meal_type_dietary` adds both fields (non-destructive; defaults make
existing rows valid with empty/`[]` values).

## B. ML extractor — `apps/audio-service`

- `app/prompt.py`: extend the JSON structure with `"meal_type": "dinner"` and
  `"dietary": ["vegetarian"]`, and add guidelines stating the **closed vocabularies**,
  that `meal_type` is a single value (or `""` if unclear), and `dietary` is an array
  (empty if none clearly apply). Only classify dietary tags the transcript supports.
- `app/extractor.py` `parse_recipe_response`: `recipe.setdefault("dietary", [])`. Add a
  normalizer that lowercases and filters `meal_type` (→ `""` if not in `MEAL_TYPES`) and
  `dietary` (drop values not in `DIETARY_TAGS`, dedupe, keep order). The audio-service has
  no Django import; it keeps its own copy of the two vocab lists (small, stable).
- `tests/test_extractor.py`: cases for valid values, unknown values dropped, casing
  normalized, dietary coerced to list, missing fields default safely.

## C. Web mapping — `apps/web/recipes/tasks.py`

In `run_extraction_job`, map onto the new fields, re-validating defensively (the web side
owns the canonical vocab):

- `meal_type=normalize_meal_type(summary.get("meal_type", ""))`
- `dietary=normalize_dietary(summary.get("dietary", []))`

`normalize_meal_type` / `normalize_dietary` live in a small `recipes/facets.py` helper
module (shared with the view and backfill command), driven by the model constants.

## D. Backfill — `apps/web/recipes/management/commands/backfill_recipe_facets.py`

For recipes where `meal_type == ""` and/or `dietary == []`, derive best-effort from the
existing `tags` JSON + title keywords:

- keyword→meal map (e.g. `breakfast/brunch → breakfast`, `dessert/cake/cookie → dessert`,
  `side → side`, else leave blank).
- keyword→diet map (`vegetarian/veggie → vegetarian`, `vegan → vegan`,
  `gluten-free/gluten free/gf → gluten_free`).

Idempotent (only fills empties), supports `--dry-run`, prints a summary count. Tested with
a small fixture set.

## E. Cookbook view — `apps/web/recipes/views.py` (`saved`)

Query params (all server-driven; no client-side filtering JS):

| param     | type            | values |
|-----------|-----------------|--------|
| `q`       | str             | substring match on `title` or `channel_name` |
| `cuisine` | multi           | cuisine strings present in the cookbook |
| `meal`    | multi           | `MEAL_TYPES` |
| `time`    | multi (buckets) | non-overlapping `cook_time_minutes` buckets: `under15` (≤15), `15-30` (>15,≤30), `30-60` (>30,≤60), `over60` (>60) |
| `creator` | multi           | `channel_name` values present in the cookbook |
| `fav`     | bool flag       | restrict to favorited recipes |
| `sort`    | enum            | `recent` (default, `-created_at`) · `quickest` (`cook_time_minutes` asc, nulls last) |
| `view`    | enum            | `grid` (default) · `list` |

**Filter semantics:** OR within a single facet's selected values; AND across facets.
`time` buckets OR together. `cook_time_minutes is NULL` matches no time bucket.

**Facet option lists + counts:** for each facet, list its distinct values with a per-value
count computed over the user's **whole cookbook** (not the post-filter set — documented
simplification). Cuisine/creator lists derive from the user's recipes; meal/time from the
fixed vocab/buckets. Empty facets (no values) are hidden. (Dietary is intentionally not a
facet in this iteration — see §A.)

**Server-rendered facet toggling:** for each option the view provides the querystring that
represents "current state with this value toggled" (helper builds it from the current
`QueryDict`). The template renders these as `hx-get` URLs targeting `#cookbook`. Active
chips, "Clear all", sort, and the grid/list toggle work the same way. Alpine only manages
dropdown open/close. Server stays the single source of truth.

Returns context: filtered+sorted `recipes`, `total` (cookbook size), `shown`, the facet
option lists with counts and active flags + toggle URLs, active-chip list, `sort`, `view`,
and `q`.

## F. Templates — `apps/web/templates/recipes/`

- `cookbook.html` — extends `base.html`, uses a wider container modifier (the cookbook
  needs more than the default 1080px `.app-main`; add a `.app-main--wide` modifier or a
  page-level wrapper). Renders the `#cookbook` wrapper around the fragment.
- `_cookbook.html` — the swappable fragment (target of every `hx-get`): count eyebrow +
  "Your cookbook" heading, sort control, grid/list toggle, the dropdown-facet toolbar,
  active-filter chips + "Clear all", then the results region (grid or list) or an empty
  state.
- `_cookbook_card.html` — grid card (`.rcard`): thumb (`<img>` when `thumbnail_url`, else
  the design's gradient fallback), `.play` glyph, `.fav` star (favorite toggle),
  `CUISINE · MEAL` `.ceyebrow`, `.rtitle` linking to `recipe_detail`, `.credit` creator,
  `.cfoot` badges (time `N MIN`/`N HR`, difficulty). No diet badge in this iteration (§A).
- `_cookbook_row.html` — list row (`.lrow`): wider thumb, eyebrow, title, creator,
  `description`, badges (time, difficulty), trailing fav star. Used when `view=list`.
- Empty states inside `_cookbook.html`:
  - cold (cookbook truly empty) → "Nothing saved yet" + Discover CTA (`.empty/.eicon/.ebtn`).
  - filtered (cookbook non-empty, zero matches) → "Nothing matches" + "Clear all".

**Favorite toggle:** `toggle_favorite` gains a `context == "cookbook"` branch returning the
re-rendered `_cookbook_card.html` (or `_cookbook_row.html` when the request carries
`view=list`) via `outerHTML` swap of `#recipe-{id}`. The Favorites-facet count refreshes on
the next filter action (documented simplification).

## G. CSS — `apps/web/static/css/components.css`

Port the 1b component classes from the design file's `<style>` block. Design tokens already
exist in `tokens.css` (same names), so rules port nearly verbatim:

`.grid3, .rcard, .rthumb, .play, .fav(.on), .ceyebrow, .rtitle, .credit, .cfoot,
.lrow, .lthumb, .ltitle, .mhead, .count, .htitle, .eyebrow, .sort, .vtog, .toolbar, .ddbtn,
.achips, .achip, .clearall, .ddmenu, .mrow, .mlabel, .mfoot, .empty, .eicon, .ebtn` plus the
`.app-main--wide` modifier. (`.diet` is deferred with the dietary badge — §A.)

Collision: the design's `.badge` differs from the existing `.badge`/`.badge--time`. Scope
the new one as `.cookbook .badge` (the fragment lives under a `.cookbook` ancestor) so
existing search/saved cards are unaffected.

## H. Testing

- `apps/web/recipes/tests/test_cookbook.py`:
  - each facet filters correctly (cuisine, meal, each time bucket, creator, fav);
  - `dietary` is populated on extraction/backfill but exposes no filter facet or badge;
  - OR-within-facet / AND-across-facets; multi-value selections;
  - both sorts (recent, quickest with null `cook_time` last);
  - `q` search on title and creator;
  - per-value counts; active chips + toggle URLs;
  - both empty states; cold vs filtered;
  - the HTMX fragment carries the `#cookbook` swap target;
  - fav toggle with `context=cookbook` returns the card and reflects new state.
- `apps/audio-service/tests/test_extractor.py`: meal/diet normalization.
- backfill command test: derives from tags/title, idempotent, `--dry-run` writes nothing.

Run: web `cd apps/web && ../../.venv-web/bin/pytest -q`; ml `cd apps/audio-service &&
../../.venv-ml/bin/pytest -q`.

## Data flow

```
ML /extract (emits meal_type, dietary)
  → tasks.run_extraction_job (normalize → Recipe.meal_type / .dietary)
  → views.saved (read query params → filter/sort, build facet lists)
  → _cookbook.html / _cookbook_card.html (eyebrow CUISINE·MEAL, diet badge)
```

## Documented simplifications

1. Facet counts are over the whole cookbook per value, not "remaining after other active
   filters."
2. Cookbook fav-toggle swaps only the affected card; the Favorites-facet count updates on
   the next filter action, not instantly.
