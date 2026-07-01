import pytest
from django.contrib.auth import get_user_model

from recipes.models import ExtractionJob, Recipe

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


def _job(user, **kw):
    kw.setdefault("source", "youtube_captions")
    kw.setdefault("status", ExtractionJob.Status.EXTRACTING)
    kw.setdefault("title", "Cacio e Pepe")
    return ExtractionJob.objects.create(owner=user, **kw)


def test_saved_shows_pending_card_unfiltered(auth_client, user):
    _job(user)
    resp = auth_client.get("/saved/")
    assert resp.status_code == 200
    assert b"EXTRACTING" in resp.content
    assert b"Cacio e Pepe" in resp.content
    # total reflects the pending card (0 recipes + 1 pending)
    assert b"1 RECIPE" in resp.content


def test_saved_hides_pending_when_filtered(auth_client, user):
    _job(user)
    resp = auth_client.get("/saved/?q=anything")
    assert resp.status_code == 200
    assert b"EXTRACTING" not in resp.content


def test_job_card_running_returns_pending(auth_client, user):
    job = _job(user)
    resp = auth_client.get(f"/jobs/{job.id}/card/")
    assert resp.status_code == 200
    assert b"EXTRACTING" in resp.content
    assert b"hx-get" in resp.content          # keeps polling


def test_pending_card_shows_video_thumbnail(auth_client, user):
    # While extracting, the card shows the source video's thumbnail (derived
    # from the video id) so it isn't a blank placeholder.
    job = _job(user, youtube_video_id="abc123")
    resp = auth_client.get(f"/jobs/{job.id}/card/")
    assert b"https://i.ytimg.com/vi/abc123/hqdefault.jpg" in resp.content


def test_pending_card_without_video_has_no_broken_image(auth_client, user):
    # A pasted-transcript job has no video -> no <img>, just the placeholder.
    job = _job(user, source="paste_transcript", youtube_video_id="")
    resp = auth_client.get(f"/jobs/{job.id}/card/")
    assert b"i.ytimg.com" not in resp.content
    assert b"<img" not in resp.content


def test_job_card_done_returns_recipe_card(auth_client, user):
    recipe = Recipe.objects.create(owner=user, title="Done Pasta")
    job = _job(user, status=ExtractionJob.Status.DONE, recipe=recipe)
    resp = auth_client.get(f"/jobs/{job.id}/card/")
    assert resp.status_code == 200
    assert b"Done Pasta" in resp.content
    assert b"EXTRACTING" not in resp.content
    assert b"hx-get" not in resp.content       # stops polling


def test_job_card_failed_stops_polling(auth_client, user):
    job = _job(user, status=ExtractionJob.Status.FAILED, error="bad transcript")
    resp = auth_client.get(f"/jobs/{job.id}/card/")
    assert resp.status_code == 200
    assert b"FAILED" in resp.content
    assert b"hx-get" not in resp.content


def test_job_card_other_user_404(auth_client, db):
    other = User.objects.create_user(email="o@e.com", password="supersecret")
    job = _job(other)
    resp = auth_client.get(f"/jobs/{job.id}/card/")
    assert resp.status_code == 404
