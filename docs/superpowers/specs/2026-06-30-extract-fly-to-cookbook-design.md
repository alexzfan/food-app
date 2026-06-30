# Extract → fly-to-cookbook + in-progress cookbook cards — design

**Date:** 2026-06-30
**Branch:** `feat/extract-fly-to-cookbook` (off `main`)
**Design source:** Claude Design project `08c47bb6-766a-4a23-b6e5-6e3899349d3d`, file
`mise/Recipe Search.dc.html` plus its companion script `mise/recipe-search-fly.js` (the
reference choreography for the fly animation, badge pop, and "In cookbook" button state).

## Goal

On the Discover search results (screens 04 grid / 04b list), clicking an **Extract** button
sends a clone of that recipe card arcing up into the **Saved** (cookbook) nav tab —
shrinking and fading as it flies — after which the tab's count badge pops (e.g. 12 → 13)
and the button settles into an **"In cookbook"** check state.

Reconciled with the real app (decided with the user):

- The animation is an **optimistic flourish**. The real Celery extraction job still fires
  on click; we **suppress the status-poller + auto-redirect** on the search page so the
  user stays on results and can keep extracting.
- The just-extracted recipe **appears in the cookbook immediately as an in-progress card**,
  styled like the rest of the cookbook, so the 12 → 13 badge bump is genuinely real. The
  placeholder self-replaces with the finished recipe card when the job completes.

Out of scope: the ingest-panel flow (`start_job`) and its `_job_status` poller (unchanged);
the standalone Favorites page; rolling the badge back if extraction fails (a failed job
renders a failed placeholder state, not a count rollback); sort/filter interplay with
placeholders beyond §D's rule.

## A. Saved-tab count badge — `base.html` + context processor

The nav lives in `apps/web/templates/base.html`; the badge must be available on every authed
page, so the count comes from a context processor rather than per-view context.

- New `apps/web/recipes/context_processors.py` → `cookbook_badge(request)`:
  - Anonymous / unauthenticated → `{}` (no badge).
  - Authed → `{"cookbook_count": Recipe.objects.filter(owner=user).count()
    + ExtractionJob.objects.filter(owner=user).exclude(
        status__in=[ExtractionJob.Status.DONE, ExtractionJob.Status.FAILED]).count()}`.
    Active (in-progress) jobs are counted because each renders as a pending cookbook card
    (§D); a finished job becomes a `Recipe` and its job flips to `DONE`, so no double-count.
- Register it in `settings.py` `TEMPLATES[...]["OPTIONS"]["context_processors"]` as
  `"recipes.context_processors.cookbook_badge"`.
- `base.html`: give the Saved link `id="saved-tab"` and append, when `cookbook_count`:
  `<span class="nav-badge" data-cookbook-badge>{{ cookbook_count }}</span>`. Badge omitted
  when the count is 0 or unset.

## B. Fly animation — `static/js/extract-fly.js`

Faithful port of `recipe-search-fly.js`, adapted to real app DOM. A single delegated
`click` listener (capture phase) on `.extract`, so it covers HTMX-swapped results:

1. Resolve the card via `btn.closest('.rcard, .rrow')` (grid card / list row) and the Saved
   tab via `#saved-tab` + its `[data-cookbook-badge]` span. If either is missing, do nothing
   (let HTMX proceed unenhanced).
2. Do **not** `preventDefault` — the form's HTMX POST must still fire (§C). The animation is
   purely additive.
3. Snapshot the card: `cloneNode(true)`, `position:fixed` over the original, append to
   `<body>`. Animate (Web Animations API) along an upward arc toward the tab center —
   `translate` to the tab, `scale 1 → ~0.46 → ~0.06`, `opacity 1 → 0`, slight rotation,
   ~880ms, `cubic-bezier(.55,0,.7,.25)`. Original card gets a small 1.015 "pop" (260ms).
4. On flight finish (guarded by a one-shot flag + `setTimeout` fallback): remove the clone,
   increment the badge text by 1 and play the springy scale pop
   (`cubic-bezier(.34,1.56,.64,1)`), and flash the tab color to accent and back.
5. Guard against double-fire with a `data-flying` flag on the button.

The **button text/state is owned by HTMX** (§C swaps in the "In cookbook" partial); the JS
only handles the clone flight + badge pop + tab flash. This keeps a clean separation and
means the feature degrades gracefully (no JS → no flight, but HTMX still shows "In cookbook"
and the badge is correct on the next full load).

Loading: add `{% block scripts %}{% endblock %}` to `base.html` just before `</body>`;
`discover.html` overrides it to `<script src="{% static 'js/extract-fly.js' %}"></script>`
(extract buttons only exist on Discover). Uses `prefers-reduced-motion`: when set, skip the
flight/pop and just bump the badge number.

## C. Extract response — `extract_from_captions` + `_extract_done.html`

`extract_from_captions` (url name `extract_recipe`) currently creates the job and returns
`_job_status.html` (poller → `HX-Redirect` to the recipe on completion). Change it to return
a new **`recipes/_extract_done.html`** instead:

- Still `fetch_transcript`; still the `_extract_fallback.html` no-captions path (unchanged);
  still `ExtractionJob.objects.create(...)` + `run_extraction_job.delay(...)`.
- Response renders `_extract_done.html`: the "In cookbook" check state — a non-interactive
  pill with a check icon and the text "In cookbook", matching the design end-state
  (`accent-soft` background, `on-soft` text, no shadow). No poller, no redirect.
- This partial swaps into `#action-{{ video.id }}` (the form's existing
  `hx-target`/`hx-swap`), replacing the Extract button.

Only the search Extract button posts to `extract_recipe`, so this change is scoped; the
ingest panel's `start_job` + `_job_status` flow is untouched.

## D. In-progress cookbook cards — `saved` view + pending partials + poll endpoint

**`saved` view (`apps/web/recipes/views.py`):** when the view is in its **default state**
(no search `q`, no facet selections, no `fav`, default sort), fetch the user's active jobs
`ExtractionJob.objects.filter(owner=user).exclude(status__in=[DONE, FAILED])` (newest first)
and pass them as `pending_jobs`; add their count to `total`. When any filter/search is
active, `pending_jobs` is empty (placeholders carry no cuisine/meal/time metadata to match,
and `total` then reflects the filtered recipe set as today). This keeps the cookbook header
count and the nav badge consistent in the unfiltered view.

**`_cookbook.html`:** above the recipe grid/list, when `pending_jobs`, render one placeholder
per job using the matching partial for the current `view`. Placeholders are pinned at the top.

**New partials** (same card/row shell as `_cookbook_card.html` / `_cookbook_row.html`, so
they sit flush in the grid/list):

- `recipes/_cookbook_pending_card.html` and `recipes/_cookbook_pending_row.html`.
- Content: the thumbnail area shows a spinner instead of the play glyph; eyebrow reads
  `EXTRACTING…`; title = `job.title`; no favorite button, no time/difficulty badges.
- Visual: a `.rcard--pending` / `.lrow--pending` modifier (subtle pulse / muted), built from
  existing tokens. Root element `id="job-{{ job.id }}"`.
- Each placeholder polls: `hx-get="{% url 'cookbook_job_card' job.id %}?view={{ view }}"`,
  `hx-trigger="load delay:1800ms"`, `hx-swap="outerHTML"` (mirrors `_job_status_poll.html`).

**New endpoint `cookbook_job_card(request, pk)`** (url name `cookbook_job_card`):

- `get_object_or_404(ExtractionJob, pk=pk, owner=request.user)`; `view` from query (`grid`
  default).
- `status == DONE` and `job.recipe_id` → render the real `_cookbook_card.html` /
  `_cookbook_row.html` for `job.recipe` (annotated via the existing `_annotated` helper so
  `is_favorite` / display helpers work). The placeholder is replaced by the finished card.
- `status == FAILED` → render a small failed placeholder (same shell, "Extraction failed"
  message, no poller) so the card stops polling.
- else → re-render the pending partial (keeps polling).

## Testing

**pytest (`apps/web`, via `.venv-web/bin/pytest`):**

- `context_processors`: count = recipes + active jobs; excludes `DONE`/`FAILED`; empty for
  anonymous users.
- `extract_from_captions`: returns the `_extract_done.html` "In cookbook" partial, still
  creates an `ExtractionJob`, still enqueues the task; no-captions still returns the fallback.
- `saved`: default view includes a pending placeholder for an active job and `total` counts
  it; with a search/filter active, placeholders are omitted.
- `cookbook_job_card`: returns the real recipe card when the job is `DONE`; returns the
  pending partial while running; returns the failed state when `FAILED`; 404 for another
  user's job.

**Visual (running-web-app skill):** confirm the fly animation + badge pop on Extract, the
"In cookbook" button end-state, and a pending card appearing in the cookbook that swaps to
the finished recipe when the job completes.

## Files touched

- `apps/web/templates/base.html` — Saved badge, `{% block scripts %}`.
- `apps/web/recipes/context_processors.py` *(new)* + `settings.py` registration.
- `apps/web/static/js/extract-fly.js` *(new)*.
- `apps/web/static/css/components.css` — `.nav-badge`, `.extract.is-saved` / "In cookbook"
  state, `.rcard--pending` / `.lrow--pending`, spinner keyframe if not already present.
- `apps/web/recipes/views.py` — `extract_from_captions` response; `saved` `pending_jobs`;
  new `cookbook_job_card`.
- `apps/web/recipes/urls.py` — `cookbook_job_card` route.
- `apps/web/templates/recipes/_extract_done.html` *(new)*.
- `apps/web/templates/recipes/_cookbook_pending_card.html` *(new)*,
  `_cookbook_pending_row.html` *(new)*.
- `apps/web/templates/recipes/_cookbook.html` — render `pending_jobs`.
- `apps/web/templates/recipes/discover.html` — load `extract-fly.js`.
