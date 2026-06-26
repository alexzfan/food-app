import pytest
from django.contrib.auth import get_user_model

from recipes.models import Favorite, Recipe

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@e.com", password="supersecret")


@pytest.fixture
def auth_client(client, user):
    client.login(username="u@e.com", password="supersecret")
    return client


def test_saved_lists_only_owner_recipes(auth_client, user):
    other = User.objects.create_user(email="o@e.com", password="supersecret")
    Recipe.objects.create(owner=user, title="Mine")
    Recipe.objects.create(owner=other, title="Theirs")
    resp = auth_client.get("/saved/")
    assert b"Mine" in resp.content
    assert b"Theirs" not in resp.content


def test_saved_search_filters(auth_client, user):
    Recipe.objects.create(owner=user, title="Tomato Soup")
    Recipe.objects.create(owner=user, title="Pancakes")
    resp = auth_client.get("/saved/", {"q": "soup"})
    assert b"Tomato Soup" in resp.content
    assert b"Pancakes" not in resp.content


def test_toggle_favorite_adds_then_removes(auth_client, user):
    r = Recipe.objects.create(owner=user, title="Pasta")
    auth_client.post(f"/recipes/{r.id}/favorite/")
    assert Favorite.objects.filter(user=user, recipe=r).exists()
    auth_client.post(f"/recipes/{r.id}/favorite/")
    assert not Favorite.objects.filter(user=user, recipe=r).exists()


def test_favorites_lists_only_favorited(auth_client, user):
    r1 = Recipe.objects.create(owner=user, title="Fav")
    Recipe.objects.create(owner=user, title="NotFav")
    Favorite.objects.create(user=user, recipe=r1)
    resp = auth_client.get("/favorites/")
    assert b"Fav" in resp.content
    assert b"NotFav" not in resp.content


def test_delete_recipe(auth_client, user):
    r = Recipe.objects.create(owner=user, title="Gone")
    resp = auth_client.post(f"/recipes/{r.id}/delete/")
    assert resp.status_code == 204
    assert not Recipe.objects.filter(pk=r.id).exists()


def test_profile_updates_display_name(auth_client, user):
    auth_client.post("/profile/", {"display_name": "Chef Alex"})
    user.refresh_from_db()
    assert user.display_name == "Chef Alex"
