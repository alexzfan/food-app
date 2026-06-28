import re

import httpx
from django.conf import settings

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

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
    return {"videos": videos, "next_page_token": data.get("nextPageToken")}
