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


def test_recipe_view_omits_credit_when_no_channel_or_video(auth_client, user):
    # No channel and no video must not render a stub "Unknown channel" credit.
    r = Recipe.objects.create(
        owner=user, title="Plain", instructions=[{"step": 1, "text": "Stir"}]
    )
    resp = auth_client.get(f"/recipes/{r.id}/")
    assert b"Unknown channel" not in resp.content
    assert b"rv-credit" not in resp.content


def test_recipe_view_credits_channel_name(auth_client, user):
    r = Recipe.objects.create(
        owner=user, title="Garlic Noodles", youtube_video_id="abc123",
        channel_name="Pasta Grannies",
        instructions=[{"step": 1, "text": "Boil"}],
    )
    resp = auth_client.get(f"/recipes/{r.id}/")
    assert b"Pasta Grannies" in resp.content
    assert b"Unknown channel" not in resp.content


def test_recipe_view_does_not_leak_iframe_template_comment(auth_client, user):
    # A multi-line {# #} comment is not recognized by Django and leaks onto the
    # page as literal text; the iframe note must be a {% comment %} block.
    r = Recipe.objects.create(
        owner=user, title="Garlic Noodles", youtube_video_id="abc123",
        instructions=[{"step": 1, "text": "Boil"}],
    )
    resp = auth_client.get(f"/recipes/{r.id}/")
    assert b"SECURE_REFERRER_POLICY" not in resp.content
    assert b"belt-and-suspenders" not in resp.content


def test_recipe_view_sends_referrer_policy_for_youtube_embed(auth_client, user):
    # Django's "same-origin" default strips the Referer on the cross-origin
    # YouTube embed and trips error 153; the app sends the origin instead.
    r = Recipe.objects.create(
        owner=user, title="Garlic Noodles", youtube_video_id="abc123",
        instructions=[{"step": 1, "text": "Boil"}],
    )
    resp = auth_client.get(f"/recipes/{r.id}/")
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
