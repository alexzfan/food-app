# apps/web/recipes/tests/test_cookbook.py
import pytest

from recipes.models import Favorite, Recipe


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(
        email="c@e.com", password="supersecret", onboarding_completed=True
    )


@pytest.fixture
def auth_client(client, user):
    client.login(username="c@e.com", password="supersecret")
    return client


def _mk(user, **kw):
    return Recipe.objects.create(owner=user, **kw)


def test_cookbook_renders_owner_recipes_with_swap_target(auth_client, user):
    _mk(user, title="Garlic Noodles")
    resp = auth_client.get("/saved/")
    assert resp.status_code == 200
    assert b"Garlic Noodles" in resp.content
    assert b'id="cookbook"' in resp.content


def test_cuisine_facet_filters(auth_client, user):
    _mk(user, title="Pasta", cuisine="italian")
    _mk(user, title="Sushi", cuisine="japanese")
    resp = auth_client.get("/saved/", {"cuisine": "italian"})
    assert b"Pasta" in resp.content
    assert b"Sushi" not in resp.content


def test_meal_facet_filters(auth_client, user):
    _mk(user, title="Eggs", meal_type="breakfast")
    _mk(user, title="Steak", meal_type="dinner")
    resp = auth_client.get("/saved/", {"meal": "breakfast"})
    assert b"Eggs" in resp.content
    assert b"Steak" not in resp.content


def test_time_bucket_filters(auth_client, user):
    _mk(user, title="Quick", cook_time_minutes=10)
    _mk(user, title="Slow", cook_time_minutes=120)
    resp = auth_client.get("/saved/", {"time": "under15"})
    assert b"Quick" in resp.content
    assert b"Slow" not in resp.content


def test_creator_facet_filters(auth_client, user):
    # NB: every creator name still appears in the creator dropdown (counts are
    # over the whole cookbook), so assert on unique recipe titles, not creators.
    _mk(user, title="KeepDish", channel_name="Lan's Kitchen")
    _mk(user, title="DropDish", channel_name="Preppy Kitchen")
    resp = auth_client.get("/saved/", {"creator": "Lan's Kitchen"})
    assert b"KeepDish" in resp.content
    assert b"DropDish" not in resp.content


def test_fav_filter(auth_client, user):
    r = _mk(user, title="Loved")
    _mk(user, title="Meh")
    Favorite.objects.create(user=user, recipe=r)
    resp = auth_client.get("/saved/", {"fav": "1"})
    assert b"Loved" in resp.content
    assert b"Meh" not in resp.content


def test_facets_are_anded_across_groups(auth_client, user):
    _mk(user, title="ItalDin", cuisine="italian", meal_type="dinner")
    _mk(user, title="ItalBrk", cuisine="italian", meal_type="breakfast")
    resp = auth_client.get("/saved/", {"cuisine": "italian", "meal": "dinner"})
    assert b"ItalDin" in resp.content
    assert b"ItalBrk" not in resp.content


def test_multiselect_within_group_is_or(auth_client, user):
    # Titles chosen so none is a substring of a cuisine value shown in the dropdown.
    _mk(user, title="DishOne", cuisine="italian")
    _mk(user, title="DishTwo", cuisine="japanese")
    _mk(user, title="DishThree", cuisine="french")
    resp = auth_client.get("/saved/", {"cuisine": ["italian", "japanese"]})
    assert b"DishOne" in resp.content and b"DishTwo" in resp.content
    assert b"DishThree" not in resp.content


def test_sort_quickest_orders_by_cook_time_nulls_last(auth_client, user):
    _mk(user, title="Slow", cook_time_minutes=90)
    _mk(user, title="Fast", cook_time_minutes=10)
    _mk(user, title="Unknown", cook_time_minutes=None)
    resp = auth_client.get("/saved/", {"sort": "quickest"})
    body = resp.content.decode()
    assert body.index("Fast") < body.index("Slow") < body.index("Unknown")


def test_search_matches_title_and_creator(auth_client, user):
    _mk(user, title="Tomato Soup")
    _mk(user, title="Pancakes", channel_name="Soupy Channel")
    _mk(user, title="Salad")
    resp = auth_client.get("/saved/", {"q": "soup"})
    assert b"Tomato Soup" in resp.content
    assert b"Pancakes" in resp.content
    assert b"Salad" not in resp.content


def test_empty_cold_state_when_no_recipes(auth_client, user):
    resp = auth_client.get("/saved/")
    assert b"Nothing saved yet" in resp.content


def test_empty_filtered_state_when_no_match(auth_client, user):
    _mk(user, title="Pasta", cuisine="italian")
    resp = auth_client.get("/saved/", {"cuisine": "thai"})
    assert b"Nothing matches" in resp.content


def test_fav_toggle_cookbook_context_returns_card(auth_client, user):
    r = _mk(user, title="Pasta")
    resp = auth_client.post(f"/recipes/{r.id}/favorite/", {"context": "cookbook"})
    assert f'id="recipe-{r.id}"'.encode() in resp.content
    assert b"fav on" in resp.content  # now favorited


def test_cook_time_display():
    assert Recipe(cook_time_minutes=15).cook_time_display == "15 MIN"
    assert Recipe(cook_time_minutes=180).cook_time_display == "3 HR"
    assert Recipe(cook_time_minutes=90).cook_time_display == "1 HR 30 MIN"
    assert Recipe(cook_time_minutes=None).cook_time_display == ""
