from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from recipes.models import ExtractionJob, Recipe, Video
from recipes.tasks import run_extraction_job

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@e.com", password="supersecret")


def test_paste_transcript_skips_whisper_and_creates_recipe(user):
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.PASTE_TRANSCRIPT, title="Pasta"
    )
    summary = {"title": "Pasta", "description": "yum", "ingredients": [{"name": "flour"}],
               "instructions": [{"step": 1, "text": "mix"}], "tags": ["italian"]}
    with patch("recipes.tasks.ml_client.extract", return_value=summary) as ex, \
         patch("recipes.tasks.ml_client.transcribe") as tr:
        run_extraction_job(job.id, transcript="boil pasta")
    tr.assert_not_called()
    ex.assert_called_once()
    job.refresh_from_db()
    assert job.status == ExtractionJob.Status.DONE
    assert job.recipe is not None
    assert Recipe.objects.get(pk=job.recipe_id).title == "Pasta"


def test_extraction_stores_youtube_transcript(user):
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.YOUTUBE_CAPTIONS,
        youtube_video_id="abc123", title="Pasta",
    )
    summary = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}
    with patch("recipes.tasks.ml_client.extract", return_value=summary):
        run_extraction_job(job.id, transcript="[0] boil pasta")
    job.refresh_from_db()
    assert Recipe.objects.get(pk=job.recipe_id).transcript == "[0] boil pasta"


def test_paste_transcript_not_persisted(user):
    # Only caption sources carry timestamps tap-to-seek needs; pasted text is
    # not stored back on the recipe.
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.PASTE_TRANSCRIPT, title="Pasta"
    )
    summary = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}
    with patch("recipes.tasks.ml_client.extract", return_value=summary):
        run_extraction_job(job.id, transcript="boil pasta")
    job.refresh_from_db()
    assert Recipe.objects.get(pk=job.recipe_id).transcript == ""


def test_extraction_credits_channel_from_cached_video(user):
    # The source channel name lives on the cached Video; extraction should
    # carry it onto the recipe so the detail view can credit it.
    Video.objects.create(
        video_id="abc123", title="Pasta vid", channel_title="Lan's Kitchen"
    )
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.YOUTUBE_CAPTIONS,
        youtube_video_id="abc123", title="Pasta",
    )
    summary = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}
    with patch("recipes.tasks.ml_client.extract", return_value=summary):
        run_extraction_job(job.id, transcript="[0] boil pasta")
    job.refresh_from_db()
    assert Recipe.objects.get(pk=job.recipe_id).channel_name == "Lan's Kitchen"


def test_extraction_leaves_channel_blank_when_video_uncached(user):
    # No cached Video (e.g. a pasted transcript) -> blank, not a crash.
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.PASTE_TRANSCRIPT, title="Pasta"
    )
    summary = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}
    with patch("recipes.tasks.ml_client.extract", return_value=summary):
        run_extraction_job(job.id, transcript="boil pasta")
    job.refresh_from_db()
    assert Recipe.objects.get(pk=job.recipe_id).channel_name == ""


def test_failure_marks_job_failed(user):
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.PASTE_TRANSCRIPT
    )
    with patch("recipes.tasks.ml_client.extract", side_effect=RuntimeError("boom")):
        run_extraction_job(job.id, transcript="x")
    job.refresh_from_db()
    assert job.status == ExtractionJob.Status.FAILED
    assert "boom" in job.error
