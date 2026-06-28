from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from recipes.models import ExtractionJob

User = get_user_model()


@pytest.fixture
def auth_client(client, db):
    User.objects.create_user(
        email="u@e.com", password="supersecret", onboarding_completed=True
    )
    client.login(username="u@e.com", password="supersecret")
    return client


def test_extract_with_captions_creates_job(auth_client):
    with patch("recipes.views.youtube.fetch_transcript", return_value="boil pasta"), \
         patch("recipes.views.run_extraction_job.delay") as delay:
        resp = auth_client.post(
            "/youtube/extract/", {"video_id": "abc", "title": "Pasta"}
        )
    assert resp.status_code == 200
    job = ExtractionJob.objects.get()
    assert job.source == ExtractionJob.Source.YOUTUBE_CAPTIONS
    assert job.youtube_video_id == "abc"
    delay.assert_called_once_with(job.id, transcript="boil pasta")


def test_extract_without_captions_shows_fallback(auth_client):
    with patch("recipes.views.youtube.fetch_transcript", return_value=None), \
         patch("recipes.views.run_extraction_job.delay") as delay:
        resp = auth_client.post(
            "/youtube/extract/", {"video_id": "abc", "title": "Pasta"}
        )
    assert resp.status_code == 200
    assert b"couldn't read captions" in resp.content.lower() \
        or b"couldn\xe2\x80\x99t read captions" in resp.content
    assert not ExtractionJob.objects.exists()
    delay.assert_not_called()


def test_extract_requires_post(auth_client):
    resp = auth_client.get("/youtube/extract/")
    assert resp.status_code == 405
