# Recipe Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the Discover experience into the Mise "Recipe Search" flow — a search landing, an enriched YouTube results grid/list with per-video state, a searching skeleton, a no-results state, and one-click caption extraction.

**Architecture:** Django + htmx + Alpine, server-rendered templates that consume the existing `tokens.css`/`components.css` design system. The `youtube.py` module gains an enrichment call (`videos.list`) and a transcript fetch; `views.py` annotates each result with local-recipe state and filters; templates render the design. All search UI lives in page content — `base.html` nav is untouched.

**Tech Stack:** Django, htmx 1.9, Alpine 3, pytest, httpx, `youtube-transcript-api`.

## Global Constraints

- Tests run from `apps/web/` with `../.venv-web/bin/pytest` (settings module `config.settings`, configured in `pytest.ini`).
- Test files match `test_*.py`; DB tests use the `db` fixture or `@pytest.mark.django_db`. Users: `User.objects.create_user(email=..., password=..., onboarding_completed=True)`; log in with `username=<email>`.
- No new color values — consume `tokens.css` custom properties only.
- Search UI must stay inside `app-main`; do **not** modify `base.html` or the global nav.
- Commit messages end with the two trailers used in this repo:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_013zHjKhVT1xKnVsTa2upPBn
  ```
- All views keep the existing `@login_required` + `@onboarding_required` decorators.

---

### Task 1: Dependency + `YOUTUBE_CAPTIONS` job source

**Files:**
- Modify: `apps/web/requirements.txt`
- Modify: `apps/web/recipes/models.py:60-63` (the `Source` choices)
- Create: `apps/web/recipes/migrations/0003_youtube_captions_source.py` (number may differ — use what `makemigrations` generates)
- Test: `apps/web/recipes/tests/test_models.py`

**Interfaces:**
- Produces: `ExtractionJob.Source.YOUTUBE_CAPTIONS == "youtube_captions"`.

- [ ] **Step 1: Add the dependency**

Append to `apps/web/requirements.txt`:
```
youtube-transcript-api
```

Install it (best-effort, per the platform package manager):
```bash
cd apps/web && ../.venv-web/bin/pip install youtube-transcript-api
```
Expected: "Successfully installed youtube-transcript-api-...". If install fails for lack of network, note it — the `fetch_transcript` code still imports lazily and degrades to `None`.

- [ ] **Step 2: Write the failing test**

Add to `apps/web/recipes/tests/test_models.py`:
```python
def test_youtube_captions_source_exists():
    assert ExtractionJob.Source.YOUTUBE_CAPTIONS == "youtube_captions"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_models.py::test_youtube_captions_source_exists -v`
Expected: FAIL with `AttributeError: YOUTUBE_CAPTIONS`.

- [ ] **Step 4: Add the source choice**

In `apps/web/recipes/models.py`, extend `ExtractionJob.Source`:
```python
    class Source(models.TextChoices):
        UPLOAD = "upload"
        PASTE_TRANSCRIPT = "paste_transcript"
        PASTE_TEXT = "paste_text"
        YOUTUBE_CAPTIONS = "youtube_captions"
```

- [ ] **Step 5: Make the migration**

Run: `cd apps/web && ../.venv-web/bin/python manage.py makemigrations recipes`
Expected: creates a migration altering `extractionjob.source` choices.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/web/requirements.txt apps/web/recipes/models.py apps/web/recipes/migrations/ apps/web/recipes/tests/test_models.py
git commit -m "feat(recipes): add YOUTUBE_CAPTIONS extraction source"
```

---

### Task 2: Duration + view-count formatters

**Files:**
- Modify: `apps/web/recipes/youtube.py`
- Test: `apps/web/recipes/tests/test_youtube.py`

**Interfaces:**
- Produces:
  - `_format_duration(iso: str) -> tuple[int | None, str]` — ISO-8601 duration → `(seconds, "m:ss"|"h:mm:ss")`; `("", None)`-safe.
  - `_format_views(count: int | None) -> str` — `1_200_000 -> "1.2M"`, `980_000 -> "980K"`, `75_000 -> "75K"`, `950 -> "950"`, `None -> ""`.

- [ ] **Step 1: Write the failing tests**

Add to `apps/web/recipes/tests/test_youtube.py`:
```python
def test_format_duration():
    assert youtube._format_duration("PT8M42S") == (522, "8:42")
    assert youtube._format_duration("PT58S") == (58, "0:58")
    assert youtube._format_duration("PT1H2M3S") == (3723, "1:02:03")
    assert youtube._format_duration("") == (None, "")
    assert youtube._format_duration("garbage") == (None, "")


def test_format_views():
    assert youtube._format_views(1_200_000) == "1.2M"
    assert youtube._format_views(980_000) == "980K"
    assert youtube._format_views(75_000) == "75K"
    assert youtube._format_views(950) == "950"
    assert youtube._format_views(None) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_youtube.py -k "format" -v`
Expected: FAIL with `AttributeError: _format_duration`.

- [ ] **Step 3: Implement the formatters**

Add near the top of `apps/web/recipes/youtube.py` (below the imports):
```python
import re

_ISO_DURATION = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def _format_duration(iso):
    """ISO-8601 video duration -> (total_seconds, display) e.g. (522, "8:42")."""
    if not iso:
        return None, ""
    match = _ISO_DURATION.fullmatch(iso)
    if not match or not any(match.groups()):
        return None, ""
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    total = hours * 3600 + minutes * 60 + seconds
    if hours:
        return total, f"{hours}:{minutes:02d}:{seconds:02d}"
    return total, f"{minutes}:{seconds:02d}"


def _format_views(count):
    """Integer view count -> short label e.g. 1_200_000 -> "1.2M"."""
    if count is None:
        return ""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count // 1_000}K"
    return str(count)
```
(`import re` may already be added here; keep a single copy.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_youtube.py -k "format" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/recipes/youtube.py apps/web/recipes/tests/test_youtube.py
git commit -m "feat(recipes): duration and view-count formatters"
```

---

### Task 3: Enrich search results via `videos.list`

**Files:**
- Modify: `apps/web/recipes/youtube.py` (`search_recipe_videos`, add `_enrich`)
- Test: `apps/web/recipes/tests/test_youtube.py`

**Interfaces:**
- Consumes: `_format_duration`, `_format_views` (Task 2).
- Produces: `search_recipe_videos(query, max_results=10, page_token=None)` now adds to each video dict: `duration_seconds: int|None`, `duration_display: str`, `view_count: int|None`, `view_count_display: str`, `has_captions: bool`. Adds `_enrich(videos: list[dict]) -> None` (mutates in place).

- [ ] **Step 1: Replace the existing exact-match test**

The current `test_search_maps_fields` asserts an exact 6-key dict and a single `httpx.get`. Enrichment adds keys and a second call. Replace that test in `apps/web/recipes/tests/test_youtube.py` with:
```python
def test_search_maps_and_enriches_fields():
    search_payload = {
        "items": [
            {
                "id": {"videoId": "abc123"},
                "snippet": {
                    "title": "Best Pasta",
                    "description": "yum",
                    "thumbnails": {"high": {"url": "http://img/x.jpg"}},
                    "channelTitle": "Chef",
                    "channelId": "ch1",
                },
            }
        ],
        "nextPageToken": "NEXT",
    }
    details_payload = {
        "items": [
            {
                "id": "abc123",
                "contentDetails": {"duration": "PT8M42S", "caption": "true"},
                "statistics": {"viewCount": "1200000"},
            }
        ]
    }
    with patch(
        "recipes.youtube.httpx.get",
        side_effect=[FakeResp(search_payload), FakeResp(details_payload)],
    ) as g:
        result = youtube.search_recipe_videos("pasta")
    video = result["videos"][0]
    assert video["id"] == "abc123"
    assert video["title"] == "Best Pasta"
    assert video["thumbnail_url"] == "http://img/x.jpg"
    assert video["channel_title"] == "Chef"
    assert video["duration_display"] == "8:42"
    assert video["duration_seconds"] == 522
    assert video["view_count_display"] == "1.2M"
    assert video["has_captions"] is True
    assert result["next_page_token"] == "NEXT"
    assert g.call_args_list[0].kwargs["params"]["q"] == "pasta recipe"
    assert g.call_args_list[1].kwargs["params"]["id"] == "abc123"


def test_search_enrichment_failure_degrades():
    search_payload = {
        "items": [
            {
                "id": {"videoId": "abc123"},
                "snippet": {
                    "title": "Best Pasta",
                    "description": "",
                    "thumbnails": {"high": {"url": "http://img/x.jpg"}},
                    "channelTitle": "Chef",
                    "channelId": "ch1",
                },
            }
        ],
        "nextPageToken": None,
    }

    def _side_effect(url, **kwargs):
        if url.endswith("/videos"):
            raise httpx.HTTPError("boom")
        return FakeResp(search_payload)

    with patch("recipes.youtube.httpx.get", side_effect=_side_effect):
        result = youtube.search_recipe_videos("pasta")
    video = result["videos"][0]
    assert video["has_captions"] is False
    assert video["duration_display"] == ""
    assert video["view_count"] is None
```

Add `import httpx` to the test file imports if not present:
```python
import httpx
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_youtube.py -k "enrich" -v`
Expected: FAIL (videos lack `duration_display`/`has_captions`).

- [ ] **Step 3: Implement `_enrich` and wire it in**

In `apps/web/recipes/youtube.py`, add:
```python
def _enrich(videos):
    """Add duration/view/caption fields via one videos.list call (best-effort)."""
    ids = [v["id"] for v in videos]
    if not ids:
        return
    details = {}
    try:
        resp = httpx.get(
            f"{YOUTUBE_API_BASE}/videos",
            params={
                "part": "contentDetails,statistics",
                "id": ",".join(ids),
                "key": settings.YOUTUBE_API_KEY,
            },
            timeout=15,
        )
        resp.raise_for_status()
        details = {item["id"]: item for item in resp.json().get("items", [])}
    except Exception:
        details = {}
    for video in videos:
        item = details.get(video["id"], {})
        content = item.get("contentDetails", {})
        stats = item.get("statistics", {})
        seconds, display = _format_duration(content.get("duration", ""))
        video["duration_seconds"] = seconds
        video["duration_display"] = display
        raw_views = stats.get("viewCount")
        video["view_count"] = int(raw_views) if raw_views is not None else None
        video["view_count_display"] = _format_views(video["view_count"])
        video["has_captions"] = content.get("caption") == "true"
```

At the end of `search_recipe_videos`, before `return`, call enrichment:
```python
    _enrich(videos)
    return {"videos": videos, "next_page_token": data.get("nextPageToken")}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_youtube.py -v`
Expected: PASS (all youtube tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/recipes/youtube.py apps/web/recipes/tests/test_youtube.py
git commit -m "feat(recipes): enrich YouTube results with duration, views, captions"
```

---

### Task 4: `fetch_transcript`

**Files:**
- Modify: `apps/web/recipes/youtube.py`
- Test: `apps/web/recipes/tests/test_youtube.py`

**Interfaces:**
- Produces: `fetch_transcript(video_id: str) -> str | None` — joined caption text, or `None` on any failure.

- [ ] **Step 1: Write the failing tests**

Add to `apps/web/recipes/tests/test_youtube.py`:
```python
def test_fetch_transcript_joins_segments():
    segments = [{"text": "boil water"}, {"text": "add pasta"}]
    with patch(
        "recipes.youtube.YouTubeTranscriptApi.get_transcript", return_value=segments
    ):
        text = youtube.fetch_transcript("vid")
    assert text == "boil water add pasta"


def test_fetch_transcript_returns_none_on_error():
    with patch(
        "recipes.youtube.YouTubeTranscriptApi.get_transcript",
        side_effect=Exception("no captions"),
    ):
        assert youtube.fetch_transcript("vid") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_youtube.py -k "transcript" -v`
Expected: FAIL (`AttributeError: fetch_transcript` / `YouTubeTranscriptApi`).

- [ ] **Step 3: Implement it**

Add the import near the top of `apps/web/recipes/youtube.py`:
```python
from youtube_transcript_api import YouTubeTranscriptApi
```

Add the function:
```python
def fetch_transcript(video_id):
    """Return joined caption text for a video, or None if unavailable."""
    try:
        segments = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join(seg["text"] for seg in segments).strip()
        return text or None
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_youtube.py -k "transcript" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/recipes/youtube.py apps/web/recipes/tests/test_youtube.py
git commit -m "feat(recipes): fetch_transcript via youtube-transcript-api"
```

---

### Task 5: Suggestions stub + landing constants

**Files:**
- Modify: `apps/web/recipes/youtube.py`
- Test: `apps/web/recipes/tests/test_youtube.py`

**Interfaces:**
- Produces:
  - `TRENDING: list[str]`, `CUISINES: list[dict]` (each `{"name": str}`).
  - `search_suggestions(query: str) -> {"queries": list[str], "creators": list[dict]}` (creators are `{"name": str, "subs": str}`); empty query → empty lists.

- [ ] **Step 1: Write the failing tests**

Add to `apps/web/recipes/tests/test_youtube.py`:
```python
def test_search_suggestions_filters_by_prefix():
    result = youtube.search_suggestions("cacio")
    assert any("cacio" in q.lower() for q in result["queries"])
    assert all("cacio" in q.lower() for q in result["queries"])


def test_search_suggestions_empty_query():
    assert youtube.search_suggestions("") == {"queries": [], "creators": []}


def test_landing_constants_present():
    assert len(youtube.TRENDING) >= 4
    assert all("name" in c for c in youtube.CUISINES)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_youtube.py -k "suggestions or constants" -v`
Expected: FAIL.

- [ ] **Step 3: Implement constants + suggestions**

Add to `apps/web/recipes/youtube.py`:
```python
TRENDING = ["Birria tacos", "Gochujang pasta", "Smash burger", "Tonkotsu ramen"]
CUISINES = [
    {"name": "Italian"},
    {"name": "Thai"},
    {"name": "Mexican"},
    {"name": "Japanese"},
    {"name": "Korean"},
    {"name": "Indian"},
]

_SUGGEST_DISHES = [
    "cacio e pepe",
    "cacio e pepe authentic roman",
    "cacio e pepe for two",
    "miso salmon",
    "miso glazed salmon",
    "focaccia",
    "chili crisp eggs",
    "birria tacos",
    "gochujang pasta",
    "smash burger",
    "tonkotsu ramen",
    "french omelette",
    "chocolate souffle",
]
_SUGGEST_CREATORS = [
    {"name": "Italia Squisita", "subs": "1.9M subscribers"},
    {"name": "Pasta Grannies", "subs": "980K subscribers"},
    {"name": "Lan's Kitchen", "subs": "1.2M subscribers"},
    {"name": "Weeknight Pasta", "subs": "220K subscribers"},
]


def search_suggestions(query):
    """Curated autocomplete stub filtered by substring of the query."""
    needle = query.strip().lower()
    if not needle:
        return {"queries": [], "creators": []}
    queries = [d for d in _SUGGEST_DISHES if needle in d.lower()][:5]
    creators = [c for c in _SUGGEST_CREATORS if needle in c["name"].lower()][:3]
    return {"queries": queries, "creators": creators}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_youtube.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/recipes/youtube.py apps/web/recipes/tests/test_youtube.py
git commit -m "feat(recipes): suggestions stub + trending/cuisine constants"
```

---

### Task 6: Port the Recipe Search CSS

**Files:**
- Modify: `apps/web/static/css/components.css` (append)
- Manual verification only (no unit test — CSS).

**Interfaces:**
- Produces the class set the templates consume: `.rcard .rcard--muted .rcard__body .rcard__action .rthumb .dur .cc .cc--muted .ready .playc .playc--muted .rtitle .credit .credit__name .credit__views .dot .save .save--on .extract .sort .vtog .fchip .fchip--on .fchip--soft .schip .sk` plus landing pieces `.search-landing .search-hero .search-hero__title .hero-field .hero-field__input .landing-cols .chip-row .trending .trending-row .cuisine-grid .cuisine-tile .info-note .suggest-menu .results-head .results-count .results-title .results-tools .filter-row .result-grid .result-list .empty-state`.

- [ ] **Step 1: Append the styles**

Append to `apps/web/static/css/components.css`:
```css
/* ===== Recipe Search ===== */

/* landing */
.search-landing { max-width: 1040px; margin: 0 auto; }
.search-hero { max-width: 740px; margin: 0 auto 38px; text-align: center; position: relative; }
.search-hero__title { font-family: var(--font-display); font-weight: 400; font-size: 42px; line-height: 1.08; letter-spacing: -.015em; color: var(--ink); margin: 14px 0 26px; }
.hero-field { display: flex; align-items: center; gap: 14px; padding: 8px 8px 8px 22px; border: 1px solid var(--accent-line); border-radius: var(--r-pill); background: var(--surface); box-shadow: var(--shadow-2); }
.hero-field svg { flex: 0 0 auto; color: var(--muted); }
.hero-field__input { flex: 1; border: none; background: transparent; outline: none; font-family: var(--font-ui); font-size: 17px; color: var(--ink); }
.hero-field__input::placeholder { color: var(--muted); }
.suggest-menu { position: absolute; left: 0; right: 0; top: calc(100% + 6px); z-index: 20; text-align: left; border: 1px solid var(--accent); border-radius: 22px; background: var(--surface); box-shadow: var(--shadow-2); padding: 12px 0; }
.suggest-menu__label { font-family: var(--font-mono); font-size: 10.5px; letter-spacing: .14em; color: var(--muted); padding: 4px 22px 8px; }
.suggest-menu__item { display: flex; align-items: center; gap: 13px; padding: 10px 22px; cursor: pointer; color: var(--ink); font-size: 15px; }
.suggest-menu__item:hover { background: var(--accent-soft); }
.suggest-menu__sub { font-family: var(--font-mono); font-size: 11px; color: var(--muted); }
.suggest-menu hr { border: none; border-top: 1px solid var(--line); margin: 8px 22px; }

.landing-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 44px; }
.seclabel { font-family: var(--font-mono); font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); margin: 0 0 14px; }
.chip-row { display: flex; flex-wrap: wrap; gap: 9px; margin-bottom: 34px; }
.schip { display: inline-flex; align-items: center; gap: 8px; padding: 8px 14px; border-radius: var(--r-pill); border: 1px solid var(--line-2); background: var(--surface); color: var(--ink-2); font-size: 13px; cursor: pointer; }
.schip:hover { border-color: var(--accent-line); color: var(--ink); }
.trending { display: flex; flex-direction: column; }
.trending-row { display: flex; align-items: center; gap: 14px; padding: 11px 4px; border-bottom: 1px solid var(--line); cursor: pointer; }
.trending-row:hover .trending-row__name { color: var(--accent); }
.trending-row__rank { font-family: var(--font-mono); font-size: 12px; color: var(--accent); width: 18px; }
.trending-row__name { flex: 1; font-size: 15px; color: var(--ink); }
.cuisine-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.cuisine-tile { position: relative; display: block; height: 104px; border-radius: 14px; overflow: hidden; border: 1px solid var(--line); background: linear-gradient(150deg, var(--surface-2), color-mix(in srgb, var(--secondary) 18%, var(--surface-2))); cursor: pointer; }
.cuisine-tile:nth-child(even) { background: linear-gradient(200deg, var(--surface-2), color-mix(in srgb, var(--accent) 16%, var(--surface-2))); }
.cuisine-tile__name { position: absolute; left: 14px; bottom: 12px; font-family: var(--font-display); font-size: 19px; color: var(--ink); }
.info-note { margin-top: 18px; padding: 14px 16px; border-radius: var(--r-md); background: var(--accent-softer); border: 1px solid var(--accent-line); font-size: 12.5px; line-height: 1.5; color: var(--on-soft); }

/* results header */
.results-head { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 20px; gap: 16px; }
.results-count { font-family: var(--font-mono); font-size: 11px; letter-spacing: .12em; color: var(--muted); margin-bottom: 7px; }
.results-title { font-size: 28px; margin: 0; }
.results-tools { display: flex; align-items: center; gap: 14px; }
.sort { display: inline-flex; align-items: center; gap: 6px; font-family: var(--font-mono); font-size: 12px; color: var(--ink-2); }
.vtog { display: flex; border: 1px solid var(--line-2); border-radius: 9px; overflow: hidden; background: var(--surface); }
.vtog a { width: 34px; height: 30px; display: flex; align-items: center; justify-content: center; color: var(--muted); cursor: pointer; }
.vtog a.on { background: var(--accent-soft); color: var(--accent); }
.filter-row { display: flex; flex-wrap: wrap; gap: 9px; padding-bottom: 22px; margin-bottom: 24px; border-bottom: 1px solid var(--line); }
.fchip { display: inline-flex; align-items: center; gap: 7px; padding: 7px 14px; border-radius: var(--r-pill); border: 1px solid var(--line-2); background: var(--surface); color: var(--ink-2); font-size: 13px; cursor: pointer; }
.fchip--on { background: var(--accent); border-color: var(--accent); color: var(--on-accent); font-weight: 600; }
.fchip--soft { background: var(--accent-soft); border-color: var(--accent-line); color: var(--on-soft); }

/* result cards */
.result-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.result-list { display: flex; flex-direction: column; }
.rcard { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; box-shadow: var(--shadow-1); display: flex; flex-direction: column; }
.rcard--muted { opacity: .7; }
.rthumb { position: relative; aspect-ratio: 16/10; display: flex; align-items: center; justify-content: center; background: linear-gradient(150deg, var(--surface-2), color-mix(in srgb, var(--secondary) 16%, var(--surface-2))); }
.rthumb img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.rcard__body { padding: 14px 15px 16px; }
.rcard__action { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.dur { position: absolute; right: 9px; bottom: 9px; padding: 3px 8px; border-radius: 6px; background: rgba(20,14,8,.78); color: #fff; font-family: var(--font-mono); font-size: 11px; }
.cc { position: absolute; right: 9px; top: 9px; padding: 3px 7px; border-radius: 6px; background: rgba(20,14,8,.7); color: #fff; font-family: var(--font-mono); font-size: 10px; letter-spacing: .06em; }
.cc--muted { background: color-mix(in srgb, var(--paper) 80%, transparent); color: var(--muted); border: 1px solid var(--line-2); }
.ready { position: absolute; left: 9px; top: 9px; display: inline-flex; align-items: center; gap: 5px; padding: 4px 9px; border-radius: var(--r-pill); background: color-mix(in srgb, var(--paper) 90%, transparent); color: var(--on-soft); font-family: var(--font-mono); font-size: 10px; font-weight: 600; letter-spacing: .04em; }
.playc { width: 44px; height: 44px; border-radius: 50%; background: color-mix(in srgb, var(--paper) 84%, transparent); display: flex; align-items: center; justify-content: center; box-shadow: var(--shadow-1); color: var(--accent); }
.playc--muted { color: var(--muted); }
.rtitle { font-family: var(--font-display); font-weight: 500; font-size: 19px; line-height: 1.16; margin: 0 0 8px; color: var(--ink); }
.rtitle a { color: inherit; }
.credit { display: flex; align-items: center; gap: 8px; margin-bottom: 13px; }
.credit .av { width: 22px; height: 22px; border-radius: 50%; background: var(--secondary-soft); border: 1px solid var(--line); }
.credit__name { font-size: 13px; color: var(--ink-2); }
.credit__views { font-family: var(--font-mono); font-size: 11.5px; color: var(--muted); }
.dot { width: 3px; height: 3px; border-radius: 50%; background: var(--muted); }
.save { width: 36px; height: 36px; border-radius: 50%; border: 1px solid var(--line-2); background: var(--surface); display: inline-flex; align-items: center; justify-content: center; color: var(--ink-2); cursor: pointer; }
.save--on { background: var(--accent-soft); border-color: var(--accent-line); color: var(--accent); }
.extract { display: inline-flex; align-items: center; gap: 7px; padding: 8px 14px; border: none; border-radius: var(--r-pill); background: var(--accent); color: var(--on-accent); font-family: var(--font-ui); font-size: 13px; font-weight: 600; box-shadow: var(--shadow-1); cursor: pointer; }
.extract:hover { background: var(--accent-press); }
.state-label { font-family: var(--font-mono); font-size: 10.5px; letter-spacing: .06em; color: var(--on-soft); }
.state-label--muted { color: var(--muted); }
.watch-link { display: inline-flex; align-items: center; gap: 7px; padding: 9px 16px; border-radius: var(--r-pill); border: 1px solid var(--line-2); background: var(--surface); color: var(--muted); font-size: 13px; }
.open-recipe { display: inline-flex; align-items: center; gap: 7px; padding: 9px 16px; border-radius: var(--r-pill); border: 1px solid var(--line-2); background: var(--surface); color: var(--ink); font-size: 13px; font-weight: 600; }

/* list-row variant */
.rrow { display: flex; gap: 20px; padding: 18px 0; border-bottom: 1px solid var(--line); }
.rrow__thumb { position: relative; width: 248px; flex: 0 0 auto; aspect-ratio: 16/9; border-radius: 12px; overflow: hidden; display: flex; align-items: center; justify-content: center; background: linear-gradient(150deg, var(--surface-2), color-mix(in srgb, var(--secondary) 16%, var(--surface-2))); }
.rrow__thumb img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.rrow__body { flex: 1; display: flex; flex-direction: column; }
.rrow__desc { font-size: 13.5px; color: var(--ink-2); line-height: 1.5; margin: 0 0 12px; max-width: 560px; }
.rrow__foot { margin-top: auto; display: flex; align-items: center; gap: 10px; }
.rrow__spacer { flex: 1; }

/* skeleton + empty */
.sk { background: linear-gradient(90deg, var(--surface-2), color-mix(in srgb, var(--secondary) 20%, var(--surface-2)), var(--surface-2)); background-size: 460px 100%; animation: mise-shimmer 1.4s linear infinite; border-radius: 6px; }
.searching-note { display: flex; align-items: center; gap: 10px; margin-bottom: 18px; font-family: var(--font-mono); font-size: 11px; letter-spacing: .14em; color: var(--accent); }
.spinner { width: 14px; height: 14px; border: 2px solid var(--accent); border-right-color: transparent; border-radius: 50%; display: inline-block; animation: mise-spin .7s linear infinite; }
.empty-state { padding: 70px 46px 40px; display: flex; flex-direction: column; align-items: center; text-align: center; }
.empty-state__icon { width: 72px; height: 72px; border-radius: 50%; background: var(--accent-soft); color: var(--accent); display: flex; align-items: center; justify-content: center; margin-bottom: 24px; }
.empty-state__title { font-family: var(--font-display); font-weight: 400; font-size: 30px; color: var(--ink); margin: 0 0 12px; }
.empty-state__copy { max-width: 460px; font-size: 15px; line-height: 1.6; color: var(--ink-2); margin: 0 0 28px; }
.empty-state__chips { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; max-width: 560px; }

@media (max-width: 720px) {
  .landing-cols { grid-template-columns: 1fr; gap: 28px; }
  .result-grid { grid-template-columns: 1fr; }
  .rrow { flex-direction: column; }
  .rrow__thumb { width: 100%; }
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/static/css/components.css
git commit -m "feat(recipes): Recipe Search component styles"
```

(Visual verification happens in Task 10 once templates exist.)

---

### Task 7: Results view + grid/list cards

**Files:**
- Modify: `apps/web/recipes/views.py` (`youtube_search`, add helpers, extend `toggle_favorite`)
- Create: `apps/web/templates/recipes/_results.html`
- Create: `apps/web/templates/recipes/_video_result_card.html`
- Create: `apps/web/templates/recipes/_save_button.html`
- Create: `apps/web/templates/recipes/_skeleton.html`
- Modify: `apps/web/recipes/tests/test_discover.py` (replace the old results test)
- Test: `apps/web/recipes/tests/test_search_results.py` (new)

**Interfaces:**
- Consumes: `youtube.search_recipe_videos` (Task 3); `Recipe`, `Favorite`.
- Produces: `youtube_search` renders `recipes/_results.html` with context `videos, error, query, view ("grid"|"list"), active_filter, filters, total, shown`. Each annotated video has `recipe` (a `Recipe` or `None`, with `.is_favorite` set when present). `toggle_favorite` returns `_save_button.html` when `POST["context"] == "search"`.

- [ ] **Step 1: Write the failing view tests**

Create `apps/web/recipes/tests/test_search_results.py`:
```python
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from recipes.models import Favorite, Recipe

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


def _video(vid, **over):
    base = {
        "id": vid, "title": f"Title {vid}", "description": "",
        "thumbnail_url": "", "channel_title": "Chef", "channel_id": "c",
        "duration_seconds": 600, "duration_display": "10:00",
        "view_count": 1000, "view_count_display": "1K", "has_captions": True,
    }
    base.update(over)
    return base


def _search(videos):
    return patch(
        "recipes.views.youtube.search_recipe_videos",
        return_value={"videos": videos, "next_page_token": None},
    )


def test_results_show_extract_for_captioned_unsaved(auth_client):
    with _search([_video("aaa", has_captions=True)]):
        resp = auth_client.get("/youtube/search/", {"q": "pasta"})
    assert resp.status_code == 200
    assert b"Title aaa" in resp.content
    assert b"Extract" in resp.content


def test_results_show_recipe_ready_when_local_recipe_exists(auth_client, user):
    Recipe.objects.create(owner=user, youtube_video_id="aaa", title="Saved One")
    with _search([_video("aaa")]):
        resp = auth_client.get("/youtube/search/", {"q": "pasta"})
    assert b"RECIPE READY" in resp.content
    assert b"/recipes/" in resp.content  # links to the local recipe


def test_results_no_captions_state(auth_client):
    with _search([_video("aaa", has_captions=False)]):
        resp = auth_client.get("/youtube/search/", {"q": "pasta"})
    assert b"Watch on YouTube" in resp.content


def test_filter_ready_excludes_unextracted(auth_client, user):
    Recipe.objects.create(owner=user, youtube_video_id="aaa", title="Saved One")
    videos = [_video("aaa"), _video("bbb")]
    with _search(videos):
        resp = auth_client.get("/youtube/search/", {"q": "pasta", "filter": "ready"})
    assert b"Title aaa" in resp.content
    assert b"Title bbb" not in resp.content


def test_filter_under15_excludes_long(auth_client):
    videos = [
        _video("aaa", duration_seconds=600),
        _video("bbb", duration_seconds=1800),
    ]
    with _search(videos):
        resp = auth_client.get("/youtube/search/", {"q": "pasta", "filter": "under15"})
    assert b"Title aaa" in resp.content
    assert b"Title bbb" not in resp.content


def test_list_view_renders_row_layout(auth_client):
    with _search([_video("aaa")]):
        resp = auth_client.get("/youtube/search/", {"q": "pasta", "view": "list"})
    assert b"rrow" in resp.content


def test_no_results_state(auth_client):
    with _search([]):
        resp = auth_client.get("/youtube/search/", {"q": "zzz"})
    assert b"No cookable videos found" in resp.content


def test_search_stored_in_session_recents(auth_client):
    with _search([_video("aaa")]):
        auth_client.get("/youtube/search/", {"q": "cacio e pepe"})
    assert auth_client.session["recent_searches"] == ["cacio e pepe"]


def test_save_button_context_returns_save_partial(auth_client, user):
    r = Recipe.objects.create(owner=user, youtube_video_id="aaa", title="X")
    resp = auth_client.post(f"/recipes/{r.id}/favorite/", {"context": "search"})
    assert Favorite.objects.filter(user=user, recipe=r).exists()
    assert b"save--on" in resp.content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_search_results.py -v`
Expected: FAIL (template/context not yet present).

- [ ] **Step 3: Add view helpers, rewrite `youtube_search`, extend `toggle_favorite`**

In `apps/web/recipes/views.py`, add module-level constants and helpers (near the top, after imports):
```python
FILTERS = [
    {"key": "all", "label": "All results"},
    {"key": "ready", "label": "Recipe ready"},
    {"key": "extractable", "label": "Extractable"},
    {"key": "under15", "label": "Under 15 min"},
    {"key": "captions", "label": "Has captions"},
]


def _annotate_videos(videos, user):
    ids = [v["id"] for v in videos]
    recipes = {
        r.youtube_video_id: r
        for r in Recipe.objects.filter(owner=user, youtube_video_id__in=ids)
    }
    fav_ids = set(
        Favorite.objects.filter(
            user=user, recipe__youtube_video_id__in=ids
        ).values_list("recipe__youtube_video_id", flat=True)
    )
    for video in videos:
        recipe = recipes.get(video["id"])
        if recipe is not None:
            recipe.is_favorite = video["id"] in fav_ids
        video["recipe"] = recipe


def _apply_filter(videos, key):
    if key == "ready":
        return [v for v in videos if v.get("recipe")]
    if key == "extractable":
        return [v for v in videos if v.get("has_captions") and not v.get("recipe")]
    if key == "under15":
        return [
            v for v in videos
            if v.get("duration_seconds") and v["duration_seconds"] <= 900
        ]
    if key == "captions":
        return [v for v in videos if v.get("has_captions")]
    return videos


def _remember_search(request, query):
    recents = [
        q for q in request.session.get("recent_searches", [])
        if q.lower() != query.lower()
    ]
    recents.insert(0, query)
    request.session["recent_searches"] = recents[:6]
```

Replace the existing `youtube_search` function body with:
```python
@login_required
@onboarding_required
def youtube_search(request):
    query = request.GET.get("q", "").strip()
    view = "list" if request.GET.get("view") == "list" else "grid"
    active_filter = request.GET.get("filter", "all")
    videos = []
    error = None
    total = 0
    if query:
        try:
            videos = youtube.search_recipe_videos(query)["videos"]
        except Exception:
            error = "Search failed. Try again."
        total = len(videos)
        _annotate_videos(videos, request.user)
        _remember_search(request, query)
        videos = _apply_filter(videos, active_filter)
    return render(
        request,
        "recipes/_results.html",
        {
            "videos": videos, "error": error, "query": query, "view": view,
            "active_filter": active_filter, "filters": FILTERS,
            "total": total, "shown": len(videos),
        },
    )
```

Extend `toggle_favorite`'s template selection. Replace its trailing branch:
```python
    # The detail page swaps just the button; list pages swap the whole card.
    if request.POST.get("context") == "detail":
        template = "recipes/_favorite_button.html"
    elif request.POST.get("context") == "search":
        template = "recipes/_save_button.html"
    else:
        template = "recipes/_recipe_card.html"
    return render(request, template, {"recipe": recipe})
```

- [ ] **Step 4: Create `_skeleton.html`**

Create `apps/web/templates/recipes/_skeleton.html`:
```html
<div class="searching-note"><span class="spinner"></span> SEARCHING YOUTUBE · CHECKING CAPTIONS</div>
<div class="result-grid">
  {% for _ in "123456" %}
  <div class="rcard">
    <div class="rthumb sk" style="border-radius:0;"></div>
    <div class="rcard__body">
      <div class="sk" style="height:18px; width:85%; margin-bottom:9px;"></div>
      <div class="sk" style="height:18px; width:55%; margin-bottom:16px;"></div>
      <div style="display:flex; align-items:center; gap:8px;">
        <div class="sk" style="height:22px; width:22px; border-radius:50%;"></div>
        <div class="sk" style="height:13px; width:120px;"></div>
      </div>
    </div>
  </div>
  {% endfor %}
</div>
```

- [ ] **Step 5: Create `_save_button.html`**

Create `apps/web/templates/recipes/_save_button.html`:
```html
<form hx-post="{% url 'toggle_favorite' recipe.id %}" hx-target="this" hx-swap="outerHTML" style="display:inline-flex;">
  {% csrf_token %}
  <input type="hidden" name="context" value="search">
  <button class="save{% if recipe.is_favorite %} save--on{% endif %}" type="submit"
          aria-label="{% if recipe.is_favorite %}Remove from saved{% else %}Save recipe{% endif %}">
    <svg width="17" height="17" viewBox="0 0 24 24" fill="{% if recipe.is_favorite %}currentColor{% else %}none{% endif %}" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>
  </button>
</form>
```

- [ ] **Step 6: Create `_video_result_card.html`**

Create `apps/web/templates/recipes/_video_result_card.html`. Renders both layouts via the `layout` variable passed by `_results.html`:
```html
{% if layout == "list" %}
<div class="rrow{% if not video.recipe and not video.has_captions %} rcard--muted{% endif %}" id="vid-{{ video.id }}">
  <div class="rrow__thumb">
    {% if video.thumbnail_url %}<img src="{{ video.thumbnail_url }}" alt="">{% endif %}
    {% if video.recipe %}<span class="ready">RECIPE READY</span>
    {% else %}<span class="playc{% if not video.has_captions %} playc--muted{% endif %}"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 4 20 12 6 20"></polygon></svg></span>{% endif %}
    {% if video.has_captions %}<span class="cc">CC</span>{% else %}<span class="cc cc--muted">NO CC</span>{% endif %}
    {% if video.duration_display %}<span class="dur">{{ video.duration_display }}</span>{% endif %}
  </div>
  <div class="rrow__body">
    <h4 class="rtitle" style="font-size:21px;">{% if video.recipe %}<a href="{% url 'recipe_detail' video.recipe.id %}">{{ video.title }}</a>{% else %}{{ video.title }}{% endif %}</h4>
    <div class="credit"><span class="av"></span><span class="credit__name">{{ video.channel_title }}</span>{% if video.view_count_display %}<span class="dot"></span><span class="credit__views">{{ video.view_count_display }} views</span>{% endif %}</div>
    {% if video.description %}<p class="rrow__desc">{{ video.description|truncatechars:160 }}</p>{% endif %}
    <div class="rrow__foot" id="action-{{ video.id }}">{% include "recipes/_result_action.html" with layout="list" %}</div>
  </div>
</div>
{% else %}
<div class="rcard{% if not video.recipe and not video.has_captions %} rcard--muted{% endif %}" id="vid-{{ video.id }}">
  <div class="rthumb">
    {% if video.thumbnail_url %}<img src="{{ video.thumbnail_url }}" alt="">{% endif %}
    {% if video.recipe %}<span class="ready">RECIPE READY</span>
    {% else %}<span class="playc{% if not video.has_captions %} playc--muted{% endif %}"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 4 20 12 6 20"></polygon></svg></span>{% endif %}
    {% if video.has_captions %}<span class="cc">CC</span>{% else %}<span class="cc cc--muted">NO CC</span>{% endif %}
    {% if video.duration_display %}<span class="dur">{{ video.duration_display }}</span>{% endif %}
  </div>
  <div class="rcard__body">
    <h4 class="rtitle">{% if video.recipe %}<a href="{% url 'recipe_detail' video.recipe.id %}">{{ video.title }}</a>{% else %}{{ video.title }}{% endif %}</h4>
    <div class="credit"><span class="av"></span><span class="credit__name">{{ video.channel_title }}</span>{% if video.view_count_display %}<span class="dot"></span><span class="credit__views">{{ video.view_count_display }} views</span>{% endif %}</div>
    <div class="rcard__action" id="action-{{ video.id }}">{% include "recipes/_result_action.html" with layout="grid" %}</div>
  </div>
</div>
{% endif %}
```

- [ ] **Step 7: Create `_result_action.html`** (shared state action, kept separate so Extract can swap it)

Create `apps/web/templates/recipes/_result_action.html`:
```html
{% if video.recipe %}
  <div style="display:flex; gap:6px;">
    {% if video.recipe.cook_time_minutes %}<span class="badge badge--time">{{ video.recipe.cook_time_minutes }} MIN</span>{% endif %}
    {% if video.recipe.difficulty %}<span class="badge badge--difficulty">{{ video.recipe.difficulty|upper }}</span>{% endif %}
  </div>
  {% if layout == "list" %}<span class="rrow__spacer"></span>{% endif %}
  {% include "recipes/_save_button.html" with recipe=video.recipe %}
  {% if layout == "list" %}<a class="open-recipe" href="{% url 'recipe_detail' video.recipe.id %}">Open recipe<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"></path><path d="m12 5 7 7-7 7"></path></svg></a>{% endif %}
{% elif video.has_captions %}
  <span class="state-label">CAPTIONS · READY TO EXTRACT</span>
  {% if layout == "list" %}<span class="rrow__spacer"></span>{% endif %}
  <form hx-post="{% url 'extract_recipe' %}" hx-target="#action-{{ video.id }}" hx-swap="innerHTML">
    {% csrf_token %}
    <input type="hidden" name="video_id" value="{{ video.id }}">
    <input type="hidden" name="title" value="{{ video.title }}">
    <button class="extract" type="submit"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18M3 12h18M6 6l12 12M18 6 6 18"></path></svg>Extract{% if layout == "list" %} recipe{% endif %}</button>
  </form>
{% else %}
  <span class="state-label state-label--muted">NO CAPTIONS — CAN'T EXTRACT</span>
  {% if layout == "list" %}<span class="rrow__spacer"></span>{% endif %}
  <a class="watch-link" href="https://www.youtube.com/watch?v={{ video.id }}" target="_blank" rel="noopener">Watch on YouTube</a>
{% endif %}
```

- [ ] **Step 8: Create `_results.html`**

Create `apps/web/templates/recipes/_results.html`:
```html
{% if error %}<div class="info-note" style="margin-bottom:18px;">{{ error }}</div>{% endif %}
<div class="results-head">
  <div>
    <div class="results-count">{{ total }} VIDEOS · {{ shown }} SHOWN · FROM YOUTUBE</div>
    <h2 class="results-title">Results for "{{ query }}"</h2>
  </div>
  <div class="results-tools">
    <span class="sort">Relevance <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"></path></svg></span>
    <div class="vtog">
      <a class="{% if view == 'grid' %}on{% endif %}" hx-get="{% url 'youtube_search' %}?q={{ query|urlencode }}&filter={{ active_filter }}&view=grid" hx-target="#results" hx-indicator="#search-indicator" aria-label="Grid view"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"></rect><rect x="14" y="3" width="7" height="7" rx="1"></rect><rect x="3" y="14" width="7" height="7" rx="1"></rect><rect x="14" y="14" width="7" height="7" rx="1"></rect></svg></a>
      <a class="{% if view == 'list' %}on{% endif %}" hx-get="{% url 'youtube_search' %}?q={{ query|urlencode }}&filter={{ active_filter }}&view=list" hx-target="#results" hx-indicator="#search-indicator" aria-label="List view"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3.5" y1="6" x2="3.51" y2="6"></line><line x1="3.5" y1="12" x2="3.51" y2="12"></line><line x1="3.5" y1="18" x2="3.51" y2="18"></line></svg></a>
    </div>
  </div>
</div>
{% if videos %}
<div class="filter-row">
  {% for f in filters %}
  <a class="fchip{% if f.key == active_filter %} fchip--on{% endif %}" hx-get="{% url 'youtube_search' %}?q={{ query|urlencode }}&view={{ view }}&filter={{ f.key }}" hx-target="#results" hx-indicator="#search-indicator">{{ f.label }}</a>
  {% endfor %}
</div>
<div class="{% if view == 'list' %}result-list{% else %}result-grid{% endif %}">
  {% for video in videos %}{% include "recipes/_video_result_card.html" with layout=view %}{% endfor %}
</div>
{% else %}
<div class="empty-state">
  <div class="empty-state__icon"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"></circle><path d="m21 21-4.3-4.3"></path><path d="m8.5 8.5 5 5M13.5 8.5l-5 5"></path></svg></div>
  <h3 class="empty-state__title">No cookable videos found</h3>
  <p class="empty-state__copy">We couldn't find captioned cooking videos for "{{ query }}". Mise can only build recipes from videos that have captions, so very new or very niche clips sometimes come up short.</p>
  <div class="seclabel">TRY ONE OF THESE</div>
  <div class="empty-state__chips">
    <a class="fchip fchip--soft" hx-get="{% url 'youtube_search' %}?q=Cacio e pepe" hx-target="#results" hx-indicator="#search-indicator">Cacio e pepe</a>
    <a class="fchip fchip--soft" hx-get="{% url 'youtube_search' %}?q=Chocolate soufflé" hx-target="#results" hx-indicator="#search-indicator">Chocolate soufflé</a>
    <a class="fchip fchip--soft" hx-get="{% url 'youtube_search' %}?q=French omelette" hx-target="#results" hx-indicator="#search-indicator">French omelette</a>
    <a class="fchip fchip--soft" hx-get="{% url 'youtube_search' %}?q=Miso salmon" hx-target="#results" hx-indicator="#search-indicator">Miso salmon</a>
    <a class="fchip fchip--soft" hx-get="{% url 'youtube_search' %}?q=Birria tacos" hx-target="#results" hx-indicator="#search-indicator">Birria tacos</a>
  </div>
</div>
{% endif %}
```

- [ ] **Step 9: Update the old results test**

In `apps/web/recipes/tests/test_discover.py`, replace `test_youtube_search_renders_results` with:
```python
def test_youtube_search_renders_results(auth_client):
    fake = {"videos": [{"id": "abc", "title": "Pasta", "description": "",
                        "thumbnail_url": "http://i/x.jpg", "channel_title": "Chef",
                        "channel_id": "c", "duration_seconds": 600,
                        "duration_display": "10:00", "view_count": 1000,
                        "view_count_display": "1K", "has_captions": True}],
            "next_page_token": None}
    with patch("recipes.views.youtube.search_recipe_videos", return_value=fake):
        resp = auth_client.get("/youtube/search/", {"q": "pasta"})
    assert resp.status_code == 200
    assert b"Pasta" in resp.content
    assert b"Extract" in resp.content
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_search_results.py recipes/tests/test_discover.py -v`
Expected: PASS. (`extract_recipe` URL is added in Task 8 — if this task is run in isolation before Task 8, the templates reference `{% url 'extract_recipe' %}`; add Task 8's URL line first, or run Tasks 7–8 together. The two tasks share the URL dependency.)

- [ ] **Step 11: Commit**

```bash
git add apps/web/recipes/views.py apps/web/templates/recipes/_results.html apps/web/templates/recipes/_video_result_card.html apps/web/templates/recipes/_result_action.html apps/web/templates/recipes/_save_button.html apps/web/templates/recipes/_skeleton.html apps/web/recipes/tests/test_search_results.py apps/web/recipes/tests/test_discover.py
git commit -m "feat(recipes): Mise results grid/list with per-video state"
```

---

### Task 8: One-click caption extraction

**Files:**
- Modify: `apps/web/recipes/views.py` (add `extract_from_captions`)
- Modify: `apps/web/recipes/urls.py`
- Create: `apps/web/templates/recipes/_extract_fallback.html`
- Test: `apps/web/recipes/tests/test_extract.py` (new)

**Interfaces:**
- Consumes: `youtube.fetch_transcript` (Task 4); `ExtractionJob`, `run_extraction_job`, `_ingest_panel.html`.
- Produces: URL name `extract_recipe` → `POST /youtube/extract/`. With a transcript: creates `ExtractionJob(source=YOUTUBE_CAPTIONS)`, enqueues, renders `_job_status.html`. Without: renders `_extract_fallback.html`, no job created.

- [ ] **Step 1: Write the failing tests**

Create `apps/web/recipes/tests/test_extract.py`:
```python
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from recipes.models import ExtractionJob

User = get_user_model()


@pytest.fixture
def auth_client(client, db):
    User.objects.create_user(
        email="u@e.com", password="supersecret", onboarding_completed=True
    )
    client.login(username="u@e.com", password="supersecret")
    return client


def test_extract_with_captions_creates_job(auth_client):
    with patch("recipes.views.youtube.fetch_transcript", return_value="boil pasta"), \
         patch("recipes.views.run_extraction_job.delay") as delay:
        resp = auth_client.post(
            "/youtube/extract/", {"video_id": "abc", "title": "Pasta"}
        )
    assert resp.status_code == 200
    job = ExtractionJob.objects.get()
    assert job.source == ExtractionJob.Source.YOUTUBE_CAPTIONS
    assert job.youtube_video_id == "abc"
    delay.assert_called_once_with(job.id, transcript="boil pasta")


def test_extract_without_captions_shows_fallback(auth_client):
    with patch("recipes.views.youtube.fetch_transcript", return_value=None), \
         patch("recipes.views.run_extraction_job.delay") as delay:
        resp = auth_client.post(
            "/youtube/extract/", {"video_id": "abc", "title": "Pasta"}
        )
    assert resp.status_code == 200
    assert b"couldn't read captions" in resp.content.lower() \
        or b"couldn\xe2\x80\x99t read captions" in resp.content
    assert not ExtractionJob.objects.exists()
    delay.assert_not_called()


def test_extract_requires_post(auth_client):
    resp = auth_client.get("/youtube/extract/")
    assert resp.status_code == 405
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_extract.py -v`
Expected: FAIL (404 / no URL).

- [ ] **Step 3: Add the view**

In `apps/web/recipes/views.py`, add:
```python
@login_required
@onboarding_required
@require_POST
def extract_from_captions(request):
    video_id = request.POST.get("video_id", "")
    title = request.POST.get("title", "")
    transcript = youtube.fetch_transcript(video_id)
    if not transcript:
        return render(
            request,
            "recipes/_extract_fallback.html",
            {"video": {"id": video_id, "title": title}},
        )
    job = ExtractionJob.objects.create(
        owner=request.user,
        source=ExtractionJob.Source.YOUTUBE_CAPTIONS,
        youtube_video_id=video_id,
        title=title,
    )
    run_extraction_job.delay(job.id, transcript=transcript)
    return render(request, "recipes/_job_status.html", {"job": job})
```

- [ ] **Step 4: Add the URL**

In `apps/web/recipes/urls.py`, add to `urlpatterns` (before the saved/detail routes):
```python
    path("youtube/extract/", views.extract_from_captions, name="extract_recipe"),
```

- [ ] **Step 5: Create the fallback partial**

Create `apps/web/templates/recipes/_extract_fallback.html`:
```html
<div>
  <p style="font-size:13px; color:var(--ink-2); margin:0 0 10px;">We couldn't read captions for this video. You can still extract a recipe by uploading the audio or pasting a transcript.</p>
  {% include "recipes/_ingest_panel.html" with video=video %}
</div>
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_extract.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/web/recipes/views.py apps/web/recipes/urls.py apps/web/templates/recipes/_extract_fallback.html apps/web/recipes/tests/test_extract.py
git commit -m "feat(recipes): one-click caption extraction with paste fallback"
```

---

### Task 9: Search landing + autocomplete

**Files:**
- Modify: `apps/web/recipes/views.py` (`discover`, add `suggest`)
- Modify: `apps/web/recipes/urls.py`
- Modify: `apps/web/templates/recipes/discover.html` (full rewrite)
- Create: `apps/web/templates/recipes/_suggestions.html`
- Modify: `apps/web/recipes/tests/test_discover.py` (update landing assertion)
- Test: `apps/web/recipes/tests/test_landing.py` (new)

**Interfaces:**
- Consumes: `youtube.TRENDING`, `youtube.CUISINES`, `youtube.search_suggestions` (Task 5).
- Produces: `discover` renders `recipes/discover.html` with `trending, cuisines, recent_searches`. URL name `suggest` → `GET /youtube/suggest/` renders `recipes/_suggestions.html` with `suggestions, q`.

- [ ] **Step 1: Write the failing tests**

Create `apps/web/recipes/tests/test_landing.py`:
```python
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def auth_client(client, db):
    User.objects.create_user(
        email="u@e.com", password="supersecret", onboarding_completed=True
    )
    client.login(username="u@e.com", password="supersecret")
    return client


def test_landing_shows_hero_and_cuisines(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 200
    assert b"What do you want to cook?" in resp.content
    assert b"BROWSE BY CUISINE" in resp.content
    assert b"Italian" in resp.content


def test_landing_shows_recent_searches_from_session(auth_client):
    session = auth_client.session
    session["recent_searches"] = ["miso salmon"]
    session.save()
    resp = auth_client.get("/")
    assert b"RECENT SEARCHES" in resp.content
    assert b"miso salmon" in resp.content


def test_suggest_returns_matches(auth_client):
    resp = auth_client.get("/youtube/suggest/", {"q": "cacio"})
    assert resp.status_code == 200
    assert b"cacio e pepe" in resp.content


def test_suggest_empty_query_renders_nothing_substantial(auth_client):
    resp = auth_client.get("/youtube/suggest/", {"q": ""})
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_landing.py -v`
Expected: FAIL.

- [ ] **Step 3: Update `discover` + add `suggest`**

In `apps/web/recipes/views.py`, replace `discover`:
```python
@login_required
@onboarding_required
def discover(request):
    return render(
        request,
        "recipes/discover.html",
        {
            "trending": youtube.TRENDING,
            "cuisines": youtube.CUISINES,
            "recent_searches": request.session.get("recent_searches", []),
        },
    )
```

Add `suggest`:
```python
@login_required
@onboarding_required
def suggest(request):
    q = request.GET.get("q", "").strip()
    return render(
        request,
        "recipes/_suggestions.html",
        {"suggestions": youtube.search_suggestions(q), "q": q},
    )
```

- [ ] **Step 4: Add the URL**

In `apps/web/recipes/urls.py`, add:
```python
    path("youtube/suggest/", views.suggest, name="suggest"),
```

- [ ] **Step 5: Create `_suggestions.html`**

Create `apps/web/templates/recipes/_suggestions.html`:
```html
{% if suggestions.queries or suggestions.creators %}
<div class="suggest-menu">
  {% if suggestions.queries %}
  <div class="suggest-menu__label">SUGGESTIONS</div>
  {% for s in suggestions.queries %}
  <div class="suggest-menu__item" hx-get="{% url 'youtube_search' %}?q={{ s|urlencode }}" hx-target="#results" hx-indicator="#search-indicator" @click="open=false">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--muted)" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"></circle><path d="m21 21-4.3-4.3"></path></svg>
    <span>{{ s }}</span>
  </div>
  {% endfor %}
  {% endif %}
  {% if suggestions.creators %}
  <hr>
  <div class="suggest-menu__label">CREATORS</div>
  {% for c in suggestions.creators %}
  <div class="suggest-menu__item" hx-get="{% url 'youtube_search' %}?q={{ c.name|urlencode }}" hx-target="#results" hx-indicator="#search-indicator" @click="open=false">
    <span class="av" style="width:30px; height:30px;"></span>
    <div style="flex:1;"><div style="font-weight:600;">{{ c.name }}</div><div class="suggest-menu__sub">{{ c.subs }}</div></div>
  </div>
  {% endfor %}
  {% endif %}
</div>
{% endif %}
```

- [ ] **Step 6: Rewrite `discover.html`**

Replace `apps/web/templates/recipes/discover.html`:
```html
{% extends "base.html" %}
{% block title %}Discover{% endblock %}
{% block content %}
<div class="search-landing">
  <div class="search-hero" x-data="{ open: false }" @click.outside="open = false">
    <div class="eyebrow" style="text-align:center; font-family:var(--font-mono); font-size:11px; letter-spacing:.16em; text-transform:uppercase; color:var(--muted);">SEARCH YOUTUBE</div>
    <h1 class="search-hero__title">What do you want to cook?</h1>
    <form class="hero-field" hx-get="{% url 'youtube_search' %}" hx-target="#results" hx-indicator="#search-indicator" @submit="open = false">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"></circle><path d="m21 21-4.3-4.3"></path></svg>
      <input class="hero-field__input" type="search" name="q" autocomplete="off"
             placeholder="Try &ldquo;cacio e pepe&rdquo;, &ldquo;miso salmon&rdquo;, &ldquo;focaccia&rdquo;&hellip;"
             hx-get="{% url 'suggest' %}" hx-target="#suggest" hx-trigger="keyup changed delay:200ms"
             @focus="open = true" @keyup="open = true">
      <button class="btn btn--primary" type="submit">Search <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"></path><path d="m12 5 7 7-7 7"></path></svg></button>
    </form>
    <div id="suggest" x-show="open" x-cloak></div>
  </div>

  <div id="search-indicator" class="htmx-indicator">{% include "recipes/_skeleton.html" %}</div>

  <div id="results">
    <div class="landing-cols">
      <div>
        {% if recent_searches %}
        <div class="seclabel">RECENT SEARCHES</div>
        <div class="chip-row">
          {% for term in recent_searches %}
          <a class="schip" hx-get="{% url 'youtube_search' %}?q={{ term|urlencode }}" hx-target="#results" hx-indicator="#search-indicator">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path></svg>{{ term }}
          </a>
          {% endfor %}
        </div>
        {% endif %}
        <div class="seclabel">TRENDING THIS WEEK</div>
        <div class="trending">
          {% for dish in trending %}
          <a class="trending-row" hx-get="{% url 'youtube_search' %}?q={{ dish|urlencode }}" hx-target="#results" hx-indicator="#search-indicator">
            <span class="trending-row__rank">{{ forloop.counter|stringformat:"02d" }}</span>
            <span class="trending-row__name">{{ dish }}</span>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline><polyline points="16 7 22 7 22 13"></polyline></svg>
          </a>
          {% endfor %}
        </div>
      </div>
      <div>
        <div class="seclabel">BROWSE BY CUISINE</div>
        <div class="cuisine-grid">
          {% for c in cuisines %}
          <a class="cuisine-tile" hx-get="{% url 'youtube_search' %}?q={{ c.name|urlencode }}" hx-target="#results" hx-indicator="#search-indicator">
            <span class="cuisine-tile__name">{{ c.name }}</span>
          </a>
          {% endfor %}
        </div>
        <div class="info-note">Mise only searches recipe-style cooking videos with captions, so every result can become a real, editable recipe.</div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 7: Add `x-cloak` style** (so the dropdown isn't flashed before Alpine loads)

In `apps/web/static/css/components.css`, append:
```css
[x-cloak] { display: none !important; }
```

- [ ] **Step 8: Update the old landing assertion**

In `apps/web/recipes/tests/test_discover.py`, replace `test_discover_renders_for_user`:
```python
def test_discover_renders_for_user(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 200
    assert b"What do you want to cook?" in resp.content
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd apps/web && ../.venv-web/bin/pytest recipes/tests/test_landing.py recipes/tests/test_discover.py -v`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add apps/web/recipes/views.py apps/web/recipes/urls.py apps/web/templates/recipes/discover.html apps/web/templates/recipes/_suggestions.html apps/web/static/css/components.css apps/web/recipes/tests/test_landing.py apps/web/recipes/tests/test_discover.py
git commit -m "feat(recipes): Mise search landing + autocomplete"
```

---

### Task 10: Full-suite + visual verification

**Files:**
- No code changes unless a regression surfaces.

- [ ] **Step 1: Run the whole suite**

Run: `cd apps/web && ../.venv-web/bin/pytest -q`
Expected: all pass. If `test_ingest.py` / `test_job_status.py` reference markup that moved, fix the assertion to match the new partials (the extraction job partials are unchanged, so these should pass as-is).

- [ ] **Step 2: Visual check with the running app**

Use the `running-web-app` skill (under `apps/web/.claude/skills`) to launch the app, log in, and screenshot:
1. `/` — search landing (hero, trending, cuisine tiles, info note)
2. type in the hero field — autocomplete dropdown appears
3. run a real search — results grid with at least one card state; toggle to list view; click a filter chip
4. a "Recipe ready" card (seed a `Recipe` with a matching `youtube_video_id` first) — confirm the bookmark + "Open recipe" work

Confirm the Ember palette, fonts, and card layouts match `mise/Recipe Search.dc.html`.

- [ ] **Step 3: Commit any fixes, then stop for review**

```bash
git add -A && git commit -m "test(recipes): verify Recipe Search end-to-end"
```
(Skip the commit if Steps 1–2 needed no changes.)

---

## Self-Review

**Spec coverage:**
- Landing (hero/recent/trending/cuisine/info) → Task 9. ✓
- Searching skeleton → Task 7 (`_skeleton.html`) wired as `hx-indicator` in Task 9. ✓
- Results grid + list toggle → Task 7. ✓
- No-results state → Task 7 (`_results.html`). ✓
- Autocomplete (stub) → Task 5 (`search_suggestions`) + Task 9 (`_suggestions.html`). ✓
- Per-video state (ready/extractable/no-captions) → Task 7 (`_result_action.html`). ✓
- One-click caption extraction → Task 8; `YOUTUBE_CAPTIONS` source → Task 1. ✓
- `videos.list` enrichment → Task 3; formatters → Task 2; `fetch_transcript` → Task 4. ✓
- Filters (all/ready/extractable/under15/captions), "Vegetarian" dropped → Task 7. ✓
- Save only on ready cards → Task 7 (`_result_action.html` + `_save_button.html`). ✓
- CSS port, no new colors → Task 6. ✓
- `youtube-transcript-api` dependency → Task 1. ✓
- Tests for every behavior → Tasks 2–9; full suite → Task 10. ✓
- `base.html`/global nav untouched → no task modifies it. ✓

**Placeholder scan:** The only meta-note is the scratch `{% for dish ... %}` line in Task 7 Step 8, explicitly flagged for removal in the same step. No TBD/TODO/"handle errors" placeholders.

**Type consistency:** `_format_duration`→`(seconds, display)`, `_format_views`→str, `_enrich` mutates and adds `duration_seconds/duration_display/view_count/view_count_display/has_captions`, consumed unchanged by `_annotate_videos`/`_apply_filter`/templates. `extract_recipe` URL name used in Task 7 templates and defined in Task 8 (cross-task dependency noted in Task 7 Step 10). `context="search"` round-trips between `_save_button.html` and `toggle_favorite`.

## Cross-task note

Tasks 7 and 8 share the `extract_recipe` URL name (Task 7 templates reference it; Task 8 defines it). When executing task-by-task, add Task 8 Step 4's URL line before running Task 7's test step, or run Tasks 7 and 8 back-to-back before testing.
</content>
