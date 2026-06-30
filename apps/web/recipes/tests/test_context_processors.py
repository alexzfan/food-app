import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from recipes.context_processors import cookbook_badge
from recipes.models import ExtractionJob, Recipe

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="u@e.com", password="supersecret", onboarding_completed=True
    )


def test_badge_counts_recipes_plus_active_jobs(rf, user):
    Recipe.objects.create(owner=user, title="A")
    Recipe.objects.create(owner=user, title="B")
    ExtractionJob.objects.create(
        owner=user, source="youtube_captions",
        status=ExtractionJob.Status.EXTRACTING,
    )
    # DONE and FAILED jobs must NOT be counted.
    ExtractionJob.objects.create(
        owner=user, source="youtube_captions", status=ExtractionJob.Status.DONE
    )
    ExtractionJob.objects.create(
        owner=user, source="youtube_captions", status=ExtractionJob.Status.FAILED
    )
    req = rf.get("/")
    req.user = user
    assert cookbook_badge(req) == {"cookbook_count": 3}


def test_badge_empty_for_anonymous(rf):
    req = rf.get("/")
    req.user = AnonymousUser()
    assert cookbook_badge(req) == {}
