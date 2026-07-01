from unittest.mock import patch

import httpx

from recipes import youtube


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


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


def test_format_duration():
    assert youtube._format_duration("PT8M42S") == (522, "8:42")
    assert youtube._format_duration("PT58S") == (58, "0:58")
    assert youtube._format_duration("PT1H2M3S") == (3723, "1:02:03")
    assert youtube._format_duration("") == (None, "")
    assert youtube._format_duration("garbage") == (None, "")


def test_thumbnail_url():
    assert youtube.thumbnail_url("abc123") == "https://i.ytimg.com/vi/abc123/hqdefault.jpg"
    assert youtube.thumbnail_url("") == ""
    assert youtube.thumbnail_url(None) == ""


def test_format_views():
    assert youtube._format_views(1_200_000) == "1.2M"
    assert youtube._format_views(980_000) == "980K"
    assert youtube._format_views(75_000) == "75K"
    assert youtube._format_views(950) == "950"
    assert youtube._format_views(None) == ""


def test_fetch_transcript_includes_timestamps():
    from youtube_transcript_api import FetchedTranscriptSnippet

    snippets = [
        FetchedTranscriptSnippet(text="boil water", start=0.0, duration=1.0),
        FetchedTranscriptSnippet(text="add pasta", start=12.7, duration=1.0),
    ]
    with patch(
        "recipes.youtube.YouTubeTranscriptApi.fetch", return_value=snippets
    ):
        text = youtube.fetch_transcript("vid")
    assert text == "[0] boil water\n[12] add pasta"


def test_fetch_transcript_returns_none_on_error():
    with patch(
        "recipes.youtube.YouTubeTranscriptApi.fetch",
        side_effect=Exception("no captions"),
    ):
        assert youtube.fetch_transcript("vid") is None


def test_fetch_transcript_empty_body_not_logged_as_error(caplog):
    # YouTube sometimes returns an empty body for the caption track, which the
    # library surfaces as an XML ParseError. That's a known/expected failure
    # (throttling or an empty track), not a code bug — don't log a traceback.
    import logging
    import xml.etree.ElementTree as ElementTree

    err = ElementTree.ParseError("no element found: line 1, column 0")
    # The recipes logger sets propagate=False (see settings.LOGGING), so attach
    # caplog's handler directly rather than relying on propagation to root.
    yt_logger = logging.getLogger("recipes.youtube")
    yt_logger.addHandler(caplog.handler)
    try:
        with patch("recipes.youtube.YouTubeTranscriptApi.fetch", side_effect=err):
            with caplog.at_level(logging.INFO, logger="recipes.youtube"):
                assert youtube.fetch_transcript("vid") is None
    finally:
        yt_logger.removeHandler(caplog.handler)

    assert not any(r.levelno >= logging.ERROR for r in caplog.records)
    assert any("empty transcript body" in r.getMessage() for r in caplog.records)


def test_search_suggestions_filters_by_prefix():
    result = youtube.search_suggestions("cacio")
    assert any("cacio" in q.lower() for q in result["queries"])
    assert all("cacio" in q.lower() for q in result["queries"])


def test_search_suggestions_empty_query():
    assert youtube.search_suggestions("") == {"queries": [], "creators": []}


def test_landing_constants_present():
    assert len(youtube.TRENDING) >= 4
    assert all("name" in c for c in youtube.CUISINES)
