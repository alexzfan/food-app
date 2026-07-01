from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from recipes import tasks
from recipes.models import Creator, ExtractionJob, Recipe, Video
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


def test_extraction_copies_thumbnail_from_cached_video(user):
    # The exact thumbnail URL lives on the cached Video; extraction should
    # carry it onto the recipe so cookbook cards render an image. Reusing the
    # same URL the Discover result loaded gives a browser-cache hit.
    Video.objects.create(
        video_id="abc123", title="Pasta vid",
        thumbnail_url="https://i.ytimg.com/vi/abc123/hqdefault.jpg",
    )
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.YOUTUBE_CAPTIONS,
        youtube_video_id="abc123", title="Pasta",
    )
    summary = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}
    with patch("recipes.tasks.ml_client.extract", return_value=summary):
        run_extraction_job(job.id, transcript="[0] boil pasta")
    job.refresh_from_db()
    assert (
        Recipe.objects.get(pk=job.recipe_id).thumbnail_url
        == "https://i.ytimg.com/vi/abc123/hqdefault.jpg"
    )


def test_extraction_derives_thumbnail_when_video_uncached(user):
    # Cache row pruned but the job still knows the video id -> derive the
    # deterministic hqdefault URL rather than leaving the card blank.
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.YOUTUBE_CAPTIONS,
        youtube_video_id="xyz789", title="Pasta",
    )
    summary = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}
    with patch("recipes.tasks.ml_client.extract", return_value=summary):
        run_extraction_job(job.id, transcript="[0] boil pasta")
    job.refresh_from_db()
    assert (
        Recipe.objects.get(pk=job.recipe_id).thumbnail_url
        == "https://i.ytimg.com/vi/xyz789/hqdefault.jpg"
    )


def test_extraction_leaves_thumbnail_blank_without_video_id(user):
    # A pasted transcript has no video -> no thumbnail, not a crash or a
    # broken image URL.
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.PASTE_TRANSCRIPT, title="Pasta"
    )
    summary = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}
    with patch("recipes.tasks.ml_client.extract", return_value=summary):
        run_extraction_job(job.id, transcript="boil pasta")
    job.refresh_from_db()
    assert Recipe.objects.get(pk=job.recipe_id).thumbnail_url == ""


def test_extraction_links_existing_creator(user):
    # The creator (with avatar) was captured during search; extraction should
    # link the recipe to that shared Creator row, not overwrite its avatar.
    Creator.objects.create(
        channel_id="ch1", title="Lan's Kitchen", avatar_url="http://av/ch1.jpg"
    )
    Video.objects.create(
        video_id="abc123", title="Pasta vid",
        channel_id="ch1", channel_title="Lan's Kitchen",
    )
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.YOUTUBE_CAPTIONS,
        youtube_video_id="abc123", title="Pasta",
    )
    summary = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}
    with patch("recipes.tasks.ml_client.extract", return_value=summary):
        run_extraction_job(job.id, transcript="[0] boil pasta")
    job.refresh_from_db()
    recipe = Recipe.objects.get(pk=job.recipe_id)
    assert recipe.creator_id == "ch1"
    assert recipe.creator.avatar_url == "http://av/ch1.jpg"


def test_extraction_creates_creator_when_absent(user):
    # Cache pruned: no Creator row yet, but the Video still knows the channel ->
    # create a bare Creator so the recipe still credits the channel.
    Video.objects.create(
        video_id="abc123", title="Pasta vid",
        channel_id="ch9", channel_title="New Chef",
    )
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.YOUTUBE_CAPTIONS,
        youtube_video_id="abc123", title="Pasta",
    )
    summary = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}
    with patch("recipes.tasks.ml_client.extract", return_value=summary):
        run_extraction_job(job.id, transcript="[0] boil pasta")
    job.refresh_from_db()
    creator = Recipe.objects.get(pk=job.recipe_id).creator
    assert creator.channel_id == "ch9"
    assert creator.title == "New Chef"


def test_extraction_leaves_creator_null_without_video(user):
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.PASTE_TRANSCRIPT, title="Pasta"
    )
    summary = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}
    with patch("recipes.tasks.ml_client.extract", return_value=summary):
        run_extraction_job(job.id, transcript="boil pasta")
    job.refresh_from_db()
    assert Recipe.objects.get(pk=job.recipe_id).creator_id is None


def test_failure_marks_job_failed(user):
    job = ExtractionJob.objects.create(
        owner=user, source=ExtractionJob.Source.PASTE_TRANSCRIPT
    )
    with patch("recipes.tasks.ml_client.extract", side_effect=RuntimeError("boom")):
        run_extraction_job(job.id, transcript="x")
    job.refresh_from_db()
    assert job.status == ExtractionJob.Status.FAILED
    assert "boom" in job.error


def test_run_extraction_job_maps_and_normalizes_facets(db, django_user_model, monkeypatch):
    user = django_user_model.objects.create_user(email="t@e.com", password="supersecret")
    job = ExtractionJob.objects.create(owner=user, source=ExtractionJob.Source.PASTE_TEXT)
    monkeypatch.setattr(tasks.ml_client, "extract", lambda transcript, title: {
        "title": "Soup", "meal_type": "Dinner", "dietary": ["Vegan", "bogus"],
    })
    tasks.run_extraction_job(job.id, transcript="some text")
    r = Recipe.objects.get(title="Soup")
    assert r.meal_type == "dinner"
    assert r.dietary == ["vegan"]
