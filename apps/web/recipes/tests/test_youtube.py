from unittest.mock import patch

from recipes import youtube


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_search_maps_fields():
    payload = {
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
    with patch("recipes.youtube.httpx.get", return_value=FakeResp(payload)) as g:
        result = youtube.search_recipe_videos("pasta")
    assert result["videos"][0] == {
        "id": "abc123",
        "title": "Best Pasta",
        "description": "yum",
        "thumbnail_url": "http://img/x.jpg",
        "channel_title": "Chef",
        "channel_id": "ch1",
    }
    assert result["next_page_token"] == "NEXT"
    # query gets " recipe" appended
    assert g.call_args.kwargs["params"]["q"] == "pasta recipe"


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
