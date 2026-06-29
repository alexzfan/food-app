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
