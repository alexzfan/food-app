# Recipe Search — design spec

**Date:** 2026-06-28
**Source design:** `mise/Recipe Search.dc.html` (Claude Design project "Mise Project")
**Branch:** `feat/mise-recipe-search` (PR into `main`)

## Goal

Restyle and extend the **Discover** experience (`recipes/discover` + `youtube_search`)
to match the Mise "Recipe Search" design: a search landing, an enriched YouTube
results grid/list with per-video state ("Recipe ready" / "Extractable" / "No
captions"), a searching skeleton, and a no-results empty state. Add one-click
caption-based extraction.

The search UI lives inside page content (`app-main`). The global nav in
`base.html` is **not** changed, so Saved / Favorites / other pages are untouched.

## Scope (from brainstorming)

In scope:
- 01 Search landing (hero search, recent searches, trending, browse-by-cuisine, info note)
- 03 Searching skeleton (htmx indicator)
- 04 Results grid + 04b Results list (grid/list toggle)
- 05 No cookable results (empty state)
- 02 Autocomplete dropdown — **stubbed** suggestions source
- One-click Extract → fetch captions → run existing extraction pipeline
- Card enrichment via a second YouTube API call (`videos.list`)

Out of scope:
- A real autocomplete/suggestions data source (curated stub only)
- "Vegetarian" filter chip (cannot be derived reliably) — omitted
- Changing the global nav / `base.html` shell

## Data sources & gaps

`recipes/youtube.search_recipe_videos` currently returns only:
`id, title, description, thumbnail_url, channel_title, channel_id`.

The design needs duration, view count, and a captions flag. These come from a
second call to YouTube `videos.list?part=contentDetails,statistics` for the
returned video IDs.

| Design element            | Source                                              |
|---------------------------|-----------------------------------------------------|
| Duration `8:42`           | `videos.list` `contentDetails.duration` (ISO 8601)  |
| View count `1.2M`         | `videos.list` `statistics.viewCount`                |
| CC / captions flag        | `videos.list` `contentDetails.caption == "true"`    |
| "Recipe ready" + link     | local `Recipe` exists for `youtube_video_id` (owner)|
| Time / difficulty badges  | the linked local `Recipe` (only shown when present) |
| Trending / cuisine        | curated constants → run real searches               |
| Recent searches           | `request.session["recent_searches"]`                |
| Autocomplete suggestions  | curated stub (`search_suggestions`)                 |

Per-video state:
- **Recipe ready** — a local `Recipe` already exists for this video → "Open recipe", save state from `Favorite`.
- **Extractable** — `has_captions and not recipe` → "Extract" button (one click).
- **No captions** — `not has_captions and not recipe` → dimmed, "Watch on YouTube".

## Backend

### `recipes/youtube.py`
- `search_recipe_videos(query, max_results, page_token)`: after the existing
  `search` call, issue one `videos.list` call for the result IDs and merge:
  - `duration_seconds: int | None`, `duration_display: str` (`m:ss` / `h:mm:ss`)
  - `view_count: int | None`, `view_count_display: str` (`1.2M`, `980K`, `75K`)
  - `has_captions: bool`
  Enrichment is best-effort: if `videos.list` fails, return base fields with
  `has_captions=False` and blank displays (search still works).
- `fetch_transcript(video_id) -> str | None`: caption text via
  `youtube-transcript-api`; joins segments; returns `None` on any failure
  (no captions, blocked, library error).
- `search_suggestions(query) -> {"queries": [...], "creators": [...]}`: curated
  stub filtered by case-insensitive prefix/substring of `query`.
- Module constants `TRENDING` (list of dish names) and `CUISINES`
  (list of `{name}`), used by the landing.

### `recipes/models.py`
- Add `ExtractionJob.Source.YOUTUBE_CAPTIONS = "youtube_captions"`. One migration.

### `recipes/views.py`
- `discover`: render landing with `trending`, `cuisines`, `recent_searches`.
- `youtube_search`: enrich videos, annotate each with `recipe` (local match),
  `is_favorite` (when recipe present); push query into session recents (cap ~6,
  dedup). Read `view` (`grid`|`list`, default `grid`) and `filter`
  (`all|ready|extractable|under15|captions`, default `all`). Apply filter in
  Python over the enriched list. Render `_results.html` with `videos`, `query`,
  `view`, `active_filter`, counts.
- `extract_from_captions` (POST, `video_id`, `title`): `fetch_transcript`;
  if text → create `ExtractionJob(source=YOUTUBE_CAPTIONS, youtube_video_id,
  title)` + `run_extraction_job.delay(job.id, transcript=text)` → render
  `_job_status.html`. If no text → render `_extract_fallback.html` (message +
  the existing upload/paste `_ingest_panel`).
- `suggest` (GET, `q`): render `_suggestions.html` from `search_suggestions`.

### `recipes/urls.py`
Add: `youtube/suggest/` → `suggest`; `youtube/extract/` → `extract_from_captions`.

## Templates

- `discover.html` — landing: hero search field (htmx GET → `youtube_search`,
  target `#results`, `hx-trigger` on submit/keyup-debounced, `hx-indicator`
  skeleton), recent-search chips, trending list, cuisine tiles, info note.
  Autocomplete: input also `hx-get` → `suggest` into a dropdown container.
- `_results.html` — results header (`N videos · M shown · from YouTube`, sort
  label, grid/list toggle), filter chips (active state via querystring), then
  grid (`repeat(3,1fr)`) or list rows of `_video_result_card.html`. Empty
  `videos` → no-results block (icon, copy, suggestion chips that re-search).
  Toggle/filter/sort links are htmx GETs preserving `q`.
- `_video_result_card.html` — one card; `layout` var (`grid`|`list`). Renders
  thumbnail (gradient placeholder + optional real thumb), duration, CC/NO-CC,
  state pill, title, channel · views, time/difficulty badges (only when a local
  recipe is present), and the state action. The save/bookmark control only
  appears on **ready** cards (it toggles `Favorite` on the local recipe via the
  existing `toggle_favorite`); extractable / no-caption cards have nothing to
  favorite yet, so no save control is shown.
  - ready → "Open recipe" link to `recipe_detail` + working save toggle
  - extractable → "Extract" button: `hx-post` → `extract_from_captions`,
    swaps the card action area with job status (polls existing
    `_job_status_poll.html`)
  - no captions → "Watch on YouTube" link
- `_skeleton.html` — skeleton card grid used as the `hx-indicator`.
- `_suggestions.html` — autocomplete dropdown (query suggestions + creators).
- `_extract_fallback.html` — caption-failure message + `_ingest_panel`.

## CSS (`static/css/components.css`)

Port the design's class set, consuming existing `tokens.css` custom properties
(no new colors): `.rcard .rthumb .dur .cc .cc--muted .ready .playc .rtitle
.credit .credit__name .credit__views .dot .badge .save .save--on .extract .sort
.vtog .fchip .fchip--on .fchip--soft .schip .sk` plus landing pieces
(hero search, `.cuisine-tile`, `.trending-row`, `.suggest-menu`) and the
`mise-shimmer`/`mise-spin`/`mise-pulse` keyframes already present in tokens.

## Dependencies

- `youtube-transcript-api` — add to `apps/web/requirements.txt`, best-effort install.

## Tests (`.venv-web/bin/pytest`, network mocked)

- `youtube.search_recipe_videos`: merges `videos.list` fields; ISO-duration →
  display; viewCount → `1.2M`; `caption` flag → `has_captions`; enrichment
  failure degrades gracefully.
- `youtube_search` view: annotates `recipe`/`is_favorite` for an existing local
  recipe; each filter (`ready`, `extractable`, `under15`, `captions`) narrows
  correctly; `view=list` renders list layout; pushes query into session recents.
- `extract_from_captions`: with transcript → creates `YOUTUBE_CAPTIONS` job and
  enqueues; without transcript → renders fallback, no job created.
- `suggest`: returns matching suggestions partial.
- `discover`: renders recent searches from session.

## Risks

- `youtube-transcript-api` can be blocked from server IPs or for caption-less
  videos. Mitigated by the `_extract_fallback` path (upload/paste still works).
- Extra `videos.list` call adds one unit of quota per search; acceptable.
</content>
</invoke>
