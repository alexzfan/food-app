import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def auth_client(client, db):
    User.objects.create_user(
        email="u@e.com", password="supersecret", onboarding_completed=True
    )
    client.login(username="u@e.com", password="supersecret")
    return client


def test_landing_shows_hero_and_cuisines(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 200
    assert b"What do you want to cook?" in resp.content
    assert b"BROWSE BY CUISINE" in resp.content
    assert b"Italian" in resp.content


def test_landing_shows_recent_searches_from_session(auth_client):
    session = auth_client.session
    session["recent_searches"] = ["miso salmon"]
    session.save()
    resp = auth_client.get("/")
    assert b"RECENT SEARCHES" in resp.content
    assert b"miso salmon" in resp.content


def test_suggest_returns_matches(auth_client):
    resp = auth_client.get("/youtube/suggest/", {"q": "cacio"})
    assert resp.status_code == 200
    assert b"cacio e pepe" in resp.content


def test_suggest_empty_query_renders_nothing_substantial(auth_client):
    resp = auth_client.get("/youtube/suggest/", {"q": ""})
    assert resp.status_code == 200
