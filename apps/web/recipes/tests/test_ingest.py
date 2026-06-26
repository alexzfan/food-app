from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from recipes.models import ExtractionJob

User = get_user_model()


@pytest.fixture
def auth_client(client, db):
    User.objects.create_user(email="u@e.com", password="supersecret")
    client.login(username="u@e.com", password="supersecret")
    return client


def test_paste_transcript_creates_job_and_enqueues(auth_client):
    with patch("recipes.views.run_extraction_job.delay") as delay:
        resp = auth_client.post("/jobs/start/", {
            "source": "paste_transcript", "youtube_video_id": "abc",
            "title": "Pasta", "transcript": "boil pasta"})
    assert resp.status_code == 200
    job = ExtractionJob.objects.get()
    assert job.source == "paste_transcript"
    delay.assert_called_once_with(job.id, transcript="boil pasta")


def test_upload_saves_file_and_enqueues(auth_client):
    with patch("recipes.views.run_extraction_job.delay") as delay:
        resp = auth_client.post("/jobs/start/", {
            "source": "upload", "youtube_video_id": "abc", "title": "Pasta",
            "media": SimpleUploadedFile("a.wav", b"fakeaudio", content_type="audio/wav")})
    assert resp.status_code == 200
    job = ExtractionJob.objects.get()
    assert delay.call_args.args[0] == job.id
    assert "file_path" in delay.call_args.kwargs
