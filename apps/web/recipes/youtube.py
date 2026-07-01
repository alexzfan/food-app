import logging
import re
from xml.etree.ElementTree import ParseError as XMLParseError

import httpx
from django.conf import settings
from youtube_transcript_api import (
    CouldNotRetrieveTranscript,
    IpBlocked,
    RequestBlocked,
    YouTubeTranscriptApi,
    YouTubeRequestFailed,
)

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# Errors worth retrying: YouTube rate-limited/blocked us or the request flaked.
# Everything else (captions disabled, none found, video unavailable) is
# permanent for this video — retrying just delays the manual fallback.
TRANSIENT_TRANSCRIPT_ERRORS = (RequestBlocked, IpBlocked, YouTubeRequestFailed)

_ISO_DURATION = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def seconds_to_display(total):
    """Total seconds -> display string e.g. 522 -> "8:42", None -> ""."""
    if total is None:
        return ""
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def thumbnail_url(video_id):
    """YouTube video id -> its hqdefault thumbnail URL, "" for a blank id.

    Matches the `high` thumbnail URL the Data API returns (see search()), so a
    card rendered from just a video id reuses the same browser-cached image the
    Discover result already loaded.
    """
    if not video_id:
        return ""
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _format_duration(iso):
    """ISO-8601 video duration -> (total_seconds, display) e.g. (522, "8:42")."""
    if not iso:
        return None, ""
    match = _ISO_DURATION.fullmatch(iso)
    if not match or not any(match.groups()):
        return None, ""
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    total = hours * 3600 + minutes * 60 + seconds
    return total, seconds_to_display(total)


def _format_views(count):
    """Integer view count -> short label e.g. 1_200_000 -> "1.2M"."""
    if count is None:
        return ""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count // 1_000}K"
    return str(count)


def search_recipe_videos(query, max_results=10, page_token=None):
    params = {
        "part": "snippet",
        "q": f"{query} recipe",
        "type": "video",
        "maxResults": str(max_results),
        "key": settings.YOUTUBE_API_KEY,
        "videoDuration": "medium",
        "relevanceLanguage": "en",
    }
    if page_token:
        params["pageToken"] = page_token

    resp = httpx.get(f"{YOUTUBE_API_BASE}/search", params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    videos = []
    for item in data.get("items", []):
        snip = item["snippet"]
        videos.append(
            {
                "id": item["id"]["videoId"],
                "title": snip["title"],
                "description": snip.get("description", ""),
                "thumbnail_url": snip["thumbnails"]["high"]["url"],
                "channel_title": snip["channelTitle"],
                "channel_id": snip["channelId"],
            }
        )
    _enrich(videos)
    return {"videos": videos, "next_page_token": data.get("nextPageToken")}


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


def fetch_transcript(video_id):
    """Return joined caption text for a video, or None if unavailable.

    Logs the underlying cause so a returned None is diagnosable: known
    "no transcript" cases at INFO/WARNING, anything unexpected with a
    traceback at ERROR.
    """
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id)
        lines = [
            f"[{int(snippet.start)}] {snippet.text.strip()}"
            for snippet in fetched
            if snippet.text and snippet.text.strip()
        ]
        text = "\n".join(lines).strip()
        if not text:
            logger.info("fetch_transcript: empty transcript for %s", video_id)
        return text or None
    except TRANSIENT_TRANSCRIPT_ERRORS as exc:
        logger.warning(
            "fetch_transcript: transient failure for %s: %s",
            video_id, type(exc).__name__,
        )
        return None
    except XMLParseError:
        # YouTube returned an empty/garbled caption body; the library parses it
        # with ElementTree.fromstring and lets the ParseError bubble (still the
        # case in 1.2.x). Usually throttling or an empty track — not a code bug.
        logger.warning("fetch_transcript: empty transcript body for %s", video_id)
        return None
    except CouldNotRetrieveTranscript as exc:
        # Captions disabled / none found / video unavailable — expected, permanent.
        logger.info(
            "fetch_transcript: no transcript for %s: %s",
            video_id, type(exc).__name__,
        )
        return None
    except Exception:
        # Unknown — could be a library/API change. Capture the traceback.
        logger.exception("fetch_transcript: unexpected error for %s", video_id)
        return None


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
