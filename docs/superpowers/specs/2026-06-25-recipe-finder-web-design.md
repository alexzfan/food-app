# Recipe Finder — Web App Design

**Date:** 2026-06-25
**Status:** Approved (design), pending implementation plan

## Summary

Replace the Expo/React Native mobile app with a web application that keeps the
same core ideas: discover cooking videos on YouTube, turn a video's spoken
content into a structured recipe via transcription + an LLM, and save / search /
favorite those recipes.

The key change from the mobile version: **ingestion no longer relies on
server-side YouTube downloading.** Pulling raw audio from YouTube with `yt-dlp`
on a server is unreliable (datacenter IP blocks, PO-token/cookie requirements,
constant breakage). Instead, the user supplies the audio: they watch the embedded
video in-app, download the audio themselves, and upload it. The server only ever
transcribes an uploaded file, which never breaks.

## Goals

- Web app preserving the core loop: search → watch → extract → save → favorite.
- Robust ingestion that does not depend on scraping YouTube.
- Consolidate on Python end-to-end (per decision), reusing the existing FastAPI
  ML service.
- Keep the recipe-extraction LLM local by default (continuing the most recent
  "local Gemma 3n" direction), with a hosted API as a swappable fallback.

## Non-Goals (v1 / YAGNI)

- Server-side YouTube audio/video downloading (`yt-dlp`). Removed.
- OAuth / social login and email verification (mobile app had these; deferred).
- Automatic in-browser audio capture from the YouTube embed — not technically
  possible (cross-origin sandboxed iframe). Manual download → upload only.
- Mobile app and the existing Express API are retired, not maintained.

## Architecture

Two services plus a database:

```
Browser (Django templates + HTMX / Alpine.js)
        │  HTML over HTTP
┌───────▼────────────────┐   HTTP   ┌──────────────────────────┐
│  Django app (apps/web) │ ───────► │  FastAPI ML service       │
│  - auth (sessions)     │          │  (apps/audio-service)     │
│  - recipes / favorites │          │  - Whisper (transcribe    │
│  - YouTube search      │          │    uploaded file)         │
│  - file uploads        │          │  - Extractor: Gemma 3n    │
│  - Celery job queue    │          │    local (default) /      │
│    + HTMX polling      │          │    hosted API (fallback)  │
└───────┬────────────────┘          └──────────────────────────┘
        │
   Postgres (users, recipes, favorites, extraction jobs)
        │
   Redis (Celery broker / result backend)
```

- **Django (`apps/web`)** — the web application: authentication, recipe/favorite
  CRUD, YouTube Data API search, upload handling, and orchestration of extraction
  jobs. Renders server-side HTML; HTMX handles live search, upload progress, and
  job-status polling.
- **FastAPI ML service (`apps/audio-service`, repurposed)** — owns the heavy
  models. Two responsibilities:
  - **Transcribe** an uploaded audio/video file with Whisper (replaces the old
    yt-dlp download path).
  - **Extract** a structured recipe from transcript text via a pluggable
    extractor: local Gemma 3n by default, hosted LLM API as fallback.
- **Postgres** — replaces Supabase. Django ORM owns the schema.
- **Redis** — Celery broker for async extraction jobs.

### Why this split

Whisper and Gemma are Python-native ML and stay isolated in one service so the
web app can scale/deploy independently of GPU/RAM-heavy inference. This mirrors
the existing `audio-service` boundary, so it is the smallest change from today's
structure while still removing the fragile yt-dlp dependency.

## Data model (Django ORM)

- **User** — Django built-in auth, email/password sessions. Replaces Supabase
  auth.
- **Recipe**
  - `title`, `description`
  - `ingredients` — JSON: `[{name, amount?, unit?, notes?}]`
  - `instructions` — JSON: `[{step, text, duration?}]`
  - `tags` — JSON/array of strings
  - `cuisine`, `cook_time_minutes`, `prep_time_minutes`, `servings`,
    `difficulty` (`easy|medium|hard`)
  - `youtube_video_id` — optional (null for non-YouTube uploads)
  - `owner` — FK → User
  - timestamps
- **Favorite** — FK → User, FK → Recipe, unique together, timestamp.
- **ExtractionJob**
  - `owner` — FK → User
  - `status` — `queued | transcribing | extracting | done | failed`
  - `progress` — optional 0–100 / step label
  - `source` — `upload | paste_transcript | paste_text`
  - `youtube_video_id` — optional, carried through to the resulting Recipe
  - `error` — optional message on failure
  - `recipe` — FK → Recipe, null until done
  - timestamps

The Recipe shape intentionally matches the mobile `RecipeSummary` /
`saveRecipe` payload so the extraction prompt and output format carry over.

## Ingestion flow (core loop)

1. **Search** — user enters a query on Discover. Django calls the YouTube Data
   API (reuse existing key/logic) → results grid (thumbnail, title, channel).
2. **Watch** — user picks a video; it plays in an embedded `<iframe>` in-app.
3. **Provide audio** — primary path: user downloads the audio/video themselves
   and uploads the file. Alternate entry points: **paste a transcript** or
   **paste recipe text** directly. (A user's own cooking video also works — the
   upload path is source-agnostic.)
4. **Job** — Django creates an `ExtractionJob` (status `queued`) and enqueues a
   Celery task. The task:
   - sends the uploaded file to the FastAPI service → Whisper → transcript
     (status `transcribing`),
   - sends the transcript to the FastAPI extractor → structured recipe
     (status `extracting`),
   - saves a `Recipe` owned by the user and marks the job `done`.
   - Paste-transcript skips Whisper; paste-text can skip straight to a saved
     Recipe or still run the extractor to structure it.
5. **Poll & reveal** — the upload response returns a job id; HTMX polls a
   job-status endpoint and renders the step label (`Transcribing… /
   Extracting…`, mirroring the mobile step UX). On `done`, it redirects to the
   recipe detail page; on `failed`, it shows the error with a retry.

### Extractor interface (pluggable)

The FastAPI service exposes a single extraction entry point backed by an
interface with two implementations:

- `LocalGemmaExtractor` — default; runs Gemma 3n locally (Ollama or
  transformers).
- `HostedExtractor` — fallback; calls a hosted LLM API.

Selection is via config/env. Both take transcript + optional video title and
return the Recipe JSON shape above. The recipe-extraction prompt carries over
from the mobile `useGemma` hook, including the JSON-only output contract and the
lenient JSON parsing (strip markdown fences, extract the first `{...}` object,
validate required `title`, default arrays).

## Pages

- **Discover** — search bar, results grid, embedded player, upload widget +
  paste-transcript / paste-text entry points, live job-status indicator.
- **Saved** — list of the user's recipes with search; favorite toggle.
- **Favorites** — favorited recipes only.
- **Recipe detail** — full recipe (ingredients, instructions, metadata); the
  source YouTube video embedded when `youtube_video_id` is present; favorite
  toggle; delete.
- **Login / Signup** — Django email/password.
- **Profile** — display name, basic account info.

## Error handling

- **Upload validation** — file type/size limits; reject overly long media
  (carry over the `MAX_DURATION_SECONDS` guard, applied to the uploaded file
  instead of a yt-dlp probe).
- **ML service failures** — Whisper or extractor errors mark the job `failed`
  with a message; the UI offers retry. Job rows are the single source of truth
  for status, so a dropped connection during the long extraction does not lose
  progress.
- **LLM JSON parse failures** — lenient parser (markdown fences, first JSON
  object, required-field validation); on unrecoverable parse failure the job
  fails with a clear message rather than saving a malformed recipe.
- **YouTube API errors** — search failures surface inline; they never block the
  upload/paste entry points.

## Testing

- **Django** — model constraints (Favorite uniqueness, Recipe ownership),
  view/permission tests (only owners see/edit their recipes), the job lifecycle
  (queued → transcribing → extracting → done/failed), and HTMX status-polling
  responses.
- **FastAPI ML service** — extractor interface with a stub/mock extractor so
  tests do not load real models; transcript→recipe parsing (reuse the mobile
  parser's edge cases: markdown fences, extra prose, missing fields); upload
  validation.
- **Integration** — end-to-end job flow with the ML service mocked, asserting a
  Recipe is created and owned correctly and that statuses transition.

## Repo changes

- **Add** `apps/web` — Django project.
- **Repurpose** `apps/audio-service` — drop `yt-dlp` download endpoints; add
  upload-transcribe and the pluggable extractor.
- **Add** Redis + update `docker-compose.yml` (web, ml service, postgres, redis,
  celery worker).
- **Retire** `apps/mobile` and `apps/api`.
- **Migrate** the recipe SQL schema concept into Django models/migrations
  (Supabase schema is reference only; Django owns the DB going forward).

## Open questions / future work

- OAuth + email verification (deferred from v1).
- Whether paste-text should always run the extractor (to structure free text)
  or allow saving raw — defaulting to running the extractor.
- GPU vs CPU hosting for local Gemma; the hosted fallback exists precisely so
  deployment is not blocked on GPU availability.
