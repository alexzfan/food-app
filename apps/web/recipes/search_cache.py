"""Global, query-keyed cache for YouTube recipe searches.

Cache-aside over the DB: a search hit is served from local rows, a miss falls
through to the live API and is persisted. Keeps us under the YouTube Data API
daily quota (search.list costs 100 units; ~99 live searches/day uncached).

Results are normalized into Video (deduped canonical metadata) + SearchResult
(ordered join) anchored by SearchQuery (the TTL clock). See models.py.
"""

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Creator, SearchQuery, SearchResult, Video

logger = logging.getLogger(__name__)

# Fields copied straight from the snippet; always present, safe to overwrite.
_SNIPPET_FIELDS = ("title", "description", "thumbnail_url", "channel_title", "channel_id")


def normalize(query):
    """Normalize a query for cache keying: trim, collapse whitespace, lowercase."""
    return " ".join(query.split()).lower()


def _is_enriched(video):
    """True if videos.list enrichment landed (duration/views/captions present)."""
    return (
        video.get("duration_seconds") is not None
        or video.get("view_count") is not None
        or video.get("has_captions")
    )


def _to_dict(video):
    """Rebuild the API-shaped dict the view/templates expect from a Video row.

    channel_avatar_url is normalized onto Creator, so it's left blank here and
    filled in bulk by cached_videos (avoids a per-row Creator query)."""
    return {
        "id": video.video_id,
        "title": video.title,
        "description": video.description,
        "thumbnail_url": video.thumbnail_url,
        "channel_title": video.channel_title,
        "channel_id": video.channel_id,
        "channel_avatar_url": "",
        "duration_seconds": video.duration_seconds,
        "duration_display": video.duration_display,
        "view_count": video.view_count,
        "view_count_display": video.view_count_display,
        "has_captions": video.has_captions,
    }


def cached_videos(query):
    """Return cached videos for a query, or None on miss/stale (caller goes live)."""
    try:
        sq = SearchQuery.objects.get(query=normalize(query))
    except SearchQuery.DoesNotExist:
        return None
    ttl = (
        settings.YOUTUBE_SEARCH_TTL
        if sq.fully_enriched
        else settings.YOUTUBE_SEARCH_UNENRICHED_TTL
    )
    if timezone.now() - sq.fetched_at > ttl:
        return None
    results = sq.results.select_related("video").order_by("rank")
    videos = [_to_dict(r.video) for r in results]
    _attach_creator_avatars(videos)
    return videos


def _attach_creator_avatars(videos):
    """Fill channel_avatar_url on rebuilt dicts from the shared Creator rows."""
    channel_ids = {v["channel_id"] for v in videos if v["channel_id"]}
    if not channel_ids:
        return
    avatars = dict(
        Creator.objects.filter(channel_id__in=channel_ids).values_list(
            "channel_id", "avatar_url"
        )
    )
    for v in videos:
        v["channel_avatar_url"] = avatars.get(v["channel_id"], "")


def search_with_cache(query, fetch):
    """Serve a search from cache, or call `fetch` (live API) on miss and persist.

    `fetch` is a zero-arg callable returning the API payload, injected so the
    caller controls the live call (and tests/patches stay at that boundary).
    """
    videos = cached_videos(query)
    if videos is not None:
        return videos
    payload = fetch()
    try:
        store(query, payload)
    except Exception:
        # Caching is best-effort: never discard a search we already paid quota for.
        logger.exception("search cache store failed for %r", query)
    return payload["videos"]


def prune(older_than=None):
    """Drop stale searches and any videos they orphaned. Returns deleted counts."""
    older_than = older_than or settings.YOUTUBE_SEARCH_PRUNE_AGE
    cutoff = timezone.now() - older_than

    stale = SearchQuery.objects.filter(fetched_at__lt=cutoff)
    n_queries = stale.count()
    stale.delete()  # cascades SearchResult, which can orphan Videos

    orphans = Video.objects.filter(appearances__isnull=True, updated_at__lt=cutoff)
    n_videos = orphans.count()
    orphans.delete()
    return {"queries": n_queries, "videos": n_videos}


@transaction.atomic
def store(query, payload):
    """Persist a live search payload into the cache, replacing any prior results."""
    key = normalize(query)
    videos = payload["videos"]
    fully_enriched = all(_is_enriched(v) for v in videos) if videos else True

    sq, _ = SearchQuery.objects.update_or_create(
        query=key,
        defaults={
            "fully_enriched": fully_enriched,
            "fetched_at": timezone.now(),
        },
    )
    sq.results.all().delete()  # result set/order can shift between refreshes

    rows = []
    for rank, v in enumerate(videos):
        snippet = {f: v[f] for f in _SNIPPET_FIELDS}
        video, _ = Video.objects.update_or_create(video_id=v["id"], defaults=snippet)
        _upsert_creator(v)
        if _is_enriched(v):
            # Only write metadata when this fetch actually has it, so a later
            # enrichment-failed fetch can't clobber good values on a shared row.
            video.duration_seconds = v["duration_seconds"]
            video.view_count = v["view_count"]
            video.has_captions = v["has_captions"]
            video.save(update_fields=["duration_seconds", "view_count", "has_captions"])
        rows.append(SearchResult(query=sq, video=video, rank=rank))
    SearchResult.objects.bulk_create(rows)
    return sq


def _upsert_creator(v):
    """Upsert the shared Creator row for a video's channel. Only overwrite the
    avatar when this payload has one, so a later avatar-less fetch (channels.list
    failed) can't wipe a good avatar off the shared row."""
    channel_id = v.get("channel_id")
    if not channel_id:
        return
    defaults = {"title": v.get("channel_title", "")}
    if v.get("channel_avatar_url"):
        defaults["avatar_url"] = v["channel_avatar_url"]
    Creator.objects.update_or_create(channel_id=channel_id, defaults=defaults)
