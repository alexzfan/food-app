# Recipe View + step→video timestamp — design spec

**Date:** 2026-06-28
**Source design:** `mise/Recipe View.dc.html` (Claude Design project `08c47bb6-…`)
**Branch:** `feat/recipe-view-timestamps` (PR into `main`)

## Goal

Replace the bare `recipes/detail.html` with the Mise **Recipe View**: a polished
recipe page with the source video, channel credit, ingredients, and a **Method**
list. The headline feature is **tap a method step to seek the embedded YouTube
video** to that step's moment, with the active step auto-highlighting as the
video plays.

That feature needs a timestamp pipeline that does not exist today: the transcript
is fetched, its per-caption timestamps are discarded, and instructions carry no
start time. This spec adds start times end-to-end, persists the transcript on the
recipe, and rebuilds the detail template.

## Scope (from brainstorming)

In scope:
- New responsive Recipe View template (one layout, not the mockup's split
  desktop+mobile DOM): header (badges, title, description, meta), left column
  (video + channel credit + ingredients card), right column (Method).
- **Tap step → seek video** (YouTube IFrame API) + active-step sync on playback.
- **Cooking mode**: "Start cooking" → Prev/Next stepper that seeks each step.
- **Share**: copy page URL → "Link copied" toast (client-side).
- **Ingredient checkboxes**: client-side ticking.
- **Save**: reuse existing `toggle_favorite` (htmx, `context=detail`), restyled.
- Timestamp pipeline: timestamped transcript → prompt `start` field →
  `instructions[].start` → view → template JS.
- Persist the (timestamped) transcript on `Recipe`.

Out of scope:
- **Servings scaling.** The +/- stepper that rescales ingredient quantities is
  omitted; "SERVES N" is shown static. Reliable scaling would need the prompt to
  emit numeric quantities (current `amount` is a free-text string) — deferred.
- Changing `base.html` shell / global nav (the app bar already lives there).
- Whisper/audio-upload timestamps (the `/transcribe` path returns no per-segment
  times; only the YouTube-captions path yields timestamps).

## Data flow

```
fetch_transcript → "[12] text" lines → ml_client.extract → prompt(start schema)
  → LLM → instructions[{step,text,start,duration?}] → parse(normalize start)
  → run_extraction_job → Recipe.instructions + Recipe.transcript
  → recipe_detail view (steps ctx) → detail.html (Alpine + YT IFrame API)
  → player.seekTo(start)
```

Start times are **best-effort and nullable** throughout, so non-YouTube sources
(upload, pasted transcript/text) and pre-existing recipes degrade gracefully.

## Backend

### `recipes/youtube.py`
- `fetch_transcript(video_id) -> str | None`: stop joining text only. Build one
  line per caption snippet as `"[<int(start)>] <text>"`, joined by `\n`
  (e.g. `[12] add the sliced garlic`). Empty/failure behavior unchanged (returns
  `None`), so caption detection and the `_extract_fallback` path still work.
  `int(start)` floors the float caption start; matches `seekTo` (int seconds).

### `apps/audio-service/app/prompt.py`
- Add `"start"` to the instruction schema: `{"step":1, "text":"…",
  "start": 12, "duration": "… (optional)"}` where `start` is **integer seconds
  or null**.
- Add a guideline: each transcript line may be prefixed with its start time in
  seconds like `[12]`; set each instruction's `start` to the seconds tag of the
  line where that step begins; use `null` when the transcript has no tags or the
  moment is unclear. Untagged transcripts (uploads/paste) → all `start: null`.

### `apps/audio-service/app/extractor.py`
- `parse_recipe_response`: normalize each instruction's `start` to `int | None`
  (coerce numeric strings/floats; non-numeric → `None`). Existing required-field
  and default behavior unchanged.

### `recipes/models.py`
- Add `Recipe.transcript = TextField(blank=True)`. **One migration.**
- Update the `instructions` comment to `# [{step, text, start?, duration?}]`
  (JSONField shape change only — no migration for that).

### `recipes/tasks.py`
- `run_extraction_job`: pass the `transcript` into `Recipe.objects.create(...)`
  via `transcript=transcript or ""`. (It is already in scope at create time,
  whether from captions or `ml_client.transcribe`.)

### `recipes/views.py`
- Add a small module-level helper `_mmss(seconds) -> str` (e.g. `135 → "2:15"`,
  `None → ""`). We do **not** reuse `youtube.seconds_to_display`: that function
  exists only on the unmerged cache branch, not on `main`, and there is no
  seconds→display helper on `main` (only `_format_duration`, which takes an ISO
  string).
- `recipe_detail`: build a `steps` context list of
  `{number, text, start, start_display}` where `start_display = _mmss(start)`.
  Pass `recipe`, `steps`, and `is_favorite` (already set).
- The credit line shows `recipe.channel_name` + a YouTube watch link only. View
  count / duration are **not** rendered — they are not stored on `Recipe` (the
  `Video` cache model is on a separate, unmerged branch). Avatar is a styled
  placeholder, matching the mockup.

## Templates

### `recipes/detail.html` — full rewrite
Extends `base.html`; page body only (global app bar stays in `base.html`).

Structure:
- Back link → `discover` (or browser back).
- Header: "AI EXTRACTED" + source/channel badges, title, description,
  `clock`/`servings`/`flame` meta row (cook time · serves · difficulty).
- Action row: **Start cooking** (primary), **Save** (htmx favorite toggle),
  **Share** (copy link). In cooking mode this row becomes the step bar
  ("STEP n OF N", Prev/Next/exit).
- Left column: video container `#yt-player`; channel credit (avatar placeholder,
  name `recipe.channel_name`, YouTube watch link); Ingredients card (header +
  static "SERVES N"; rows with a client-side checkbox). (Views/duration are
  omitted — not stored on `Recipe`; see the views section.)
- Right column: **Method** — `steps` rendered as rows; each row shows the step
  number disc, text, and (when `start` is not null **and** a video exists) a
  "JUMP TO m:ss" chip. Active step shows "PLAYING · m:ss" and accent styling.

One Alpine `x-data` component (`recipeView`) ported from the mockup's logic:
- Loads the YouTube IFrame API (`https://www.youtube.com/iframe_api`), creates a
  player on `#yt-player` from `recipe.youtube_video_id`.
- `seek(sec)` → `player.seekTo(sec, true); player.playVideo()`.
- Poll `getCurrentTime()` (~500ms) → set `activeStep` to the last step whose
  `start <= t`.
- Step click → `seek(step.start)` + set active.
- Cooking mode: `start cooking` sets `cooking=true`, seeks step 1; Prev/Next
  clamp and seek.
- Checkboxes: local `checked` map.
- Share: `navigator.clipboard.writeText(location.href)` → `shared` toast (~1.8s).
- No video (`youtube_video_id` empty): skip player creation; steps render without
  jump chips; cooking mode still walks step text (no seek).

## CSS (`static/css/components.css`)

Add a `.recipe-view` scoped block consuming existing `tokens.css` vars (no new
colors): header/meta, action buttons (`primary`/`secondary`/`fav` pill variants),
cooking step bar, video frame, channel credit, ingredients card + checkbox rows,
method step rows (default/active), step number disc, jump/playing chip,
"Link copied" toast, and the responsive two-column → single-column grid.

## Graceful degradation

| Condition | Behavior |
|-----------|----------|
| No `youtube_video_id` | No player; no jump chips; cooking mode walks text only |
| Instruction `start` is null | That step: no chip, no seek on click |
| Recipe extracted before this change | All `start` null → behaves as no-timestamp |
| No view count / duration on Recipe | Credit shows channel name + watch link only |

## Tests

### audio-service (`.venv-ml`, `apps/audio-service/tests`)
- `build_prompt` output contains the `start` field/instruction text.
- `parse_recipe_response`: instruction `start` coerced to `int`; non-numeric →
  `None`; missing `start` tolerated; existing title/defaults behavior intact.

### web (`.venv-web`, `apps/web/recipes/tests`)
- `fetch_transcript`: with a mocked `YouTubeTranscriptApi` returning snippets,
  output is `[seconds] text` lines; empty → `None`.
- `run_extraction_job`: created `Recipe.transcript` equals the transcript used.
- `recipe_detail`: renders `steps` with `start_display` and jump chips for a
  recipe with video + timestamps; renders cleanly with no video / null starts.

## Risks

- LLM may mis-assign or omit `start`. Nullable + graceful degradation keep the
  page correct; a wrong jump is low-stakes (user re-taps / scrubs).
- YouTube IFrame API is a third-party script; player creation is guarded and the
  page is fully usable without it (static steps, watch-on-YouTube link).
- Persisting transcripts grows row size; transcripts are text and bounded by
  video length — acceptable.
- **Migration numbering:** `main` is at migration `0002`, so this feature adds
  `0003_recipe_transcript`. The unmerged cache branch also adds a `0003_*`
  migration; whichever lands second will need `manage.py makemigrations --merge`
  to reconcile the two `0003` leaves. Expected and standard for parallel
  branches — not a blocker.
