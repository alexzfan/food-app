import pytest
from django.contrib.auth import get_user_model

from recipes.models import Recipe

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


def test_cookbook_card_has_stretched_link_to_detail(auth_client, user):
    recipe = Recipe.objects.create(owner=user, title="Cacio e Pepe")
    body = auth_client.get("/saved/").content.decode()
    # the whole card is clickable via a stretched link on the title
    assert 'class="card-link"' in body
    assert f"/recipes/{recipe.id}/" in body


def test_cookbook_list_row_has_stretched_link_to_detail(auth_client, user):
    recipe = Recipe.objects.create(owner=user, title="Cacio e Pepe")
    body = auth_client.get("/saved/?view=list").content.decode()
    assert 'class="card-link"' in body
    assert f"/recipes/{recipe.id}/" in body
