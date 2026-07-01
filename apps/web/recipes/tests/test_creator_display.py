import pytest
from django.contrib.auth import get_user_model

from recipes.models import Creator, Recipe

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


def _recipe(user, **kw):
    kw.setdefault("title", "Cacio e Pepe")
    kw.setdefault("channel_name", "Lan's Kitchen")
    return Recipe.objects.create(owner=user, **kw)


def test_saved_renders_creator_avatar(auth_client, user):
    creator = Creator.objects.create(
        channel_id="ch1", title="Lan's Kitchen", avatar_url="http://av/ch1.jpg"
    )
    _recipe(user, creator=creator)
    resp = auth_client.get("/saved/")
    assert resp.status_code == 200
    assert b"http://av/ch1.jpg" in resp.content


def test_detail_renders_creator_avatar(auth_client, user):
    creator = Creator.objects.create(
        channel_id="ch1", title="Lan's Kitchen", avatar_url="http://av/ch1.jpg"
    )
    recipe = _recipe(user, creator=creator)
    resp = auth_client.get(f"/recipes/{recipe.id}/")
    assert resp.status_code == 200
    assert b"http://av/ch1.jpg" in resp.content


def test_saved_no_avatar_leaves_plain_circle(auth_client, user):
    # No creator -> credit still shows, just the plain avatar placeholder.
    _recipe(user)
    resp = auth_client.get("/saved/")
    assert resp.status_code == 200
    assert b"background-image" not in resp.content
