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
