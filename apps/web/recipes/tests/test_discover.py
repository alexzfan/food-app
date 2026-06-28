from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def auth_client(client, db):
    User.objects.create_user(email="u@e.com", password="supersecret", onboarding_completed=True)
    client.login(username="u@e.com", password="supersecret")
    return client


def test_discover_requires_login(client, db):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login/" in resp["Location"]


def test_discover_renders_for_user(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 200
    assert b"Discover recipes" in resp.content


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
