import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from recipes.models import ExtractionJob, Favorite, Recipe

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@e.com", password="supersecret")


def test_recipe_defaults(user):
    r = Recipe.objects.create(owner=user, title="Pasta")
    assert r.ingredients == []
    assert r.instructions == []
    assert r.tags == []
    assert r.youtube_video_id == ""


def test_favorite_unique_per_user_recipe(user):
    r = Recipe.objects.create(owner=user, title="Pasta")
    Favorite.objects.create(user=user, recipe=r)
    with pytest.raises(IntegrityError):
        Favorite.objects.create(user=user, recipe=r)


def test_extraction_job_starts_queued(user):
    job = ExtractionJob.objects.create(owner=user, source=ExtractionJob.Source.UPLOAD)
    assert job.status == ExtractionJob.Status.QUEUED
    assert job.recipe is None


def test_youtube_captions_source_exists():
    assert ExtractionJob.Source.YOUTUBE_CAPTIONS == "youtube_captions"
