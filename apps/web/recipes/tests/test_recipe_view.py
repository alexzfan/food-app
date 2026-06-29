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


def test_recipe_detail_builds_step_context(auth_client, user):
    r = Recipe.objects.create(
        owner=user, title="Garlic Noodles", youtube_video_id="abc123",
        instructions=[
            {"step": 1, "text": "Boil", "start": 12},
            {"step": 2, "text": "Melt", "start": 108},
            {"step": 3, "text": "Toss"},
        ],
    )
    resp = auth_client.get(f"/recipes/{r.id}/")
    assert resp.status_code == 200
    steps = resp.context["steps"]
    assert [s["start"] for s in steps] == [12, 108, None]
    assert steps[0]["start_display"] == "0:12"
    assert steps[1]["start_display"] == "1:48"
    assert steps[2]["start_display"] == ""
    assert resp.context["rv_data"] == {"videoId": "abc123", "steps": [12, 108, None]}


def test_recipe_view_renders_jump_chips(auth_client, user):
    r = Recipe.objects.create(
        owner=user, title="Garlic Noodles", youtube_video_id="abc123",
        channel_name="Lan's Kitchen",
        instructions=[{"step": 1, "text": "Boil noodles", "start": 12}],
    )
    resp = auth_client.get(f"/recipes/{r.id}/")
    body = resp.content
    assert b"Boil noodles" in body
    assert b"JUMP TO 0:12" in body
    assert b"Start cooking" in body
    assert b"Share" in body
    assert b'id="yt-player"' in body


def test_recipe_view_handles_legacy_string_instructions(auth_client, user):
    # Older recipes stored instructions as plain strings, not dicts.
    r = Recipe.objects.create(
        owner=user, title="Old", instructions=["Just stir well"]
    )
    resp = auth_client.get(f"/recipes/{r.id}/")
    assert resp.status_code == 200
    steps = resp.context["steps"]
    assert steps[0]["text"] == "Just stir well"
    assert steps[0]["start"] is None
    assert b"Just stir well" in resp.content


def test_recipe_view_without_video_has_no_chip_or_player(auth_client, user):
    r = Recipe.objects.create(
        owner=user, title="Plain", instructions=[{"step": 1, "text": "Stir well"}]
    )
    resp = auth_client.get(f"/recipes/{r.id}/")
    body = resp.content
    assert resp.status_code == 200
    assert b"Stir well" in body
    assert b"JUMP TO" not in body
    assert b'id="yt-player"' not in body
