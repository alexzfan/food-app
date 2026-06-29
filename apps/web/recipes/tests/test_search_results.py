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


def test_repeat_search_served_from_cache(auth_client):
    with patch(
        "recipes.views.youtube.search_recipe_videos",
        return_value={"videos": [_video("aaa")], "next_page_token": None},
    ) as mock:
        first = auth_client.get("/youtube/search/", {"q": "pasta"})
        second = auth_client.get("/youtube/search/", {"q": "pasta"})
    assert b"Title aaa" in first.content
    assert b"Title aaa" in second.content
    assert mock.call_count == 1  # second request served from the DB cache


def test_save_button_context_returns_save_partial(auth_client, user):
    r = Recipe.objects.create(owner=user, youtube_video_id="aaa", title="X")
    resp = auth_client.post(f"/recipes/{r.id}/favorite/", {"context": "search"})
    assert Favorite.objects.filter(user=user, recipe=r).exists()
    assert b"save--on" in resp.content
