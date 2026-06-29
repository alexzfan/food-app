from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from recipes import search_cache
from recipes.models import SearchQuery, Video


def _vid(vid, **over):
    base = {
        "id": vid, "title": f"Title {vid}", "description": "d",
        "thumbnail_url": "http://img/x.jpg", "channel_title": "Chef",
        "channel_id": "ch1", "duration_seconds": 600, "duration_display": "10:00",
        "view_count": 1000, "view_count_display": "1K", "has_captions": True,
    }
    base.update(over)
    return base


def _payload(videos, token=None):
    return {"videos": videos, "next_page_token": token}


def test_video_duration_display_derived_from_seconds():
    assert Video(duration_seconds=522).duration_display == "8:42"
    assert Video(duration_seconds=3723).duration_display == "1:02:03"
    assert Video(duration_seconds=None).duration_display == ""


def test_video_view_count_display_derived():
    assert Video(view_count=1_200_000).view_count_display == "1.2M"
    assert Video(view_count=75_000).view_count_display == "75K"
    assert Video(view_count=None).view_count_display == ""


def test_store_creates_video_query_and_results(db):
    search_cache.store("Pasta Carbonara", _payload([_vid("a"), _vid("b")], token="NEXT"))
    sq = SearchQuery.objects.get()
    assert sq.query == "pasta carbonara"
    assert not hasattr(sq, "next_page_token")  # token in payload is ignored, not stored
    assert Video.objects.count() == 2
    results = list(sq.results.order_by("rank"))
    assert [r.video_id for r in results] == ["a", "b"]
    assert [r.rank for r in results] == [0, 1]


def test_store_normalizes_whitespace_and_case(db):
    search_cache.store("  Pasta   Carbonara  ", _payload([_vid("a")]))
    assert SearchQuery.objects.get().query == "pasta carbonara"


def test_store_dedupes_videos_across_queries(db):
    search_cache.store("pasta", _payload([_vid("a")]))
    search_cache.store("carbonara", _payload([_vid("a")]))
    assert Video.objects.count() == 1
    assert SearchQuery.objects.count() == 2


def test_store_replaces_results_on_refresh(db):
    search_cache.store("pasta", _payload([_vid("a"), _vid("b")]))
    search_cache.store("pasta", _payload([_vid("c")]))
    sq = SearchQuery.objects.get()
    assert [r.video_id for r in sq.results.all()] == ["c"]


def test_store_marks_query_unenriched_when_metadata_missing(db):
    bad = _vid("a", duration_seconds=None, view_count=None, has_captions=False)
    search_cache.store("pasta", _payload([bad]))
    assert SearchQuery.objects.get().fully_enriched is False


def test_store_does_not_clobber_enriched_metadata(db):
    search_cache.store("pasta", _payload([_vid("a", duration_seconds=600, view_count=999)]))
    bad = _vid("a", duration_seconds=None, view_count=None, has_captions=False)
    search_cache.store("carbonara", _payload([bad]))
    v = Video.objects.get(video_id="a")
    assert v.duration_seconds == 600
    assert v.view_count == 999


def test_cached_videos_miss_returns_none(db):
    assert search_cache.cached_videos("nothing cached") is None


def test_cached_videos_returns_dicts_in_rank_order(db):
    search_cache.store("pasta", _payload([_vid("a"), _vid("b")]))
    videos = search_cache.cached_videos("pasta")
    assert [v["id"] for v in videos] == ["a", "b"]
    first = videos[0]
    assert set(first) >= {
        "id", "title", "description", "thumbnail_url", "channel_title",
        "channel_id", "duration_seconds", "duration_display",
        "view_count", "view_count_display", "has_captions",
    }
    assert first["duration_display"] == "10:00"
    assert first["view_count_display"] == "1K"


def test_cached_videos_normalizes_query(db):
    search_cache.store("Pasta", _payload([_vid("a")]))
    assert search_cache.cached_videos("  pasta ") is not None


def test_cached_videos_expired_returns_none(db, settings):
    search_cache.store("pasta", _payload([_vid("a")]))
    sq = SearchQuery.objects.get()
    sq.fetched_at = timezone.now() - settings.YOUTUBE_SEARCH_TTL - timedelta(seconds=1)
    sq.save(update_fields=["fetched_at"])
    assert search_cache.cached_videos("pasta") is None


def test_cached_videos_unenriched_uses_short_ttl(db, settings):
    bad = _vid("a", duration_seconds=None, view_count=None, has_captions=False)
    search_cache.store("pasta", _payload([bad]))
    sq = SearchQuery.objects.get()
    # Still within the full TTL, but past the shorter un-enriched window.
    sq.fetched_at = (
        timezone.now() - settings.YOUTUBE_SEARCH_UNENRICHED_TTL - timedelta(seconds=1)
    )
    sq.save(update_fields=["fetched_at"])
    assert search_cache.cached_videos("pasta") is None


def test_search_with_cache_fetches_on_miss_then_serves_from_cache(db):
    calls = []

    def fetch():
        calls.append(1)
        return _payload([_vid("a")])

    first = search_cache.search_with_cache("pasta", fetch)
    second = search_cache.search_with_cache("pasta", fetch)
    assert [v["id"] for v in first] == ["a"]
    assert [v["id"] for v in second] == ["a"]
    assert len(calls) == 1  # second call served from cache, no live fetch


def test_search_with_cache_returns_results_even_if_store_fails(db):
    # A cache-write failure must not discard a successful (already-paid-for) search.
    with patch("recipes.search_cache.store", side_effect=Exception("db down")):
        videos = search_cache.search_with_cache("pasta", lambda: _payload([_vid("a")]))
    assert [v["id"] for v in videos] == ["a"]


def test_prune_deletes_stale_queries_and_orphan_videos(db):
    search_cache.store("old", _payload([_vid("old_vid")]))
    search_cache.store("fresh", _payload([_vid("fresh_vid")]))
    aged = timezone.now() - timedelta(days=400)
    SearchQuery.objects.filter(query="old").update(fetched_at=aged)
    Video.objects.filter(video_id="old_vid").update(updated_at=aged)

    search_cache.prune(older_than=timedelta(days=90))

    assert not SearchQuery.objects.filter(query="old").exists()
    assert not Video.objects.filter(video_id="old_vid").exists()  # orphaned, aged
    assert SearchQuery.objects.filter(query="fresh").exists()
    assert Video.objects.filter(video_id="fresh_vid").exists()


def test_prune_keeps_aged_video_still_referenced_by_fresh_query(db):
    # Same video in both an aged query and a fresh one: must survive prune.
    search_cache.store("old", _payload([_vid("shared")]))
    search_cache.store("fresh", _payload([_vid("shared")]))
    aged = timezone.now() - timedelta(days=400)
    SearchQuery.objects.filter(query="old").update(fetched_at=aged)
    Video.objects.filter(video_id="shared").update(updated_at=aged)

    search_cache.prune(older_than=timedelta(days=90))

    assert Video.objects.filter(video_id="shared").exists()  # fresh query still refs it
