import httpx
from django.conf import settings

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


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
