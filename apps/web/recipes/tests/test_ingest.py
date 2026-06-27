from pathlib import Path
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from recipes.models import ExtractionJob, Recipe
from recipes.tasks import run_extraction_job

User = get_user_model()


@pytest.fixture
def auth_client(client, db):
    User.objects.create_user(email="u@e.com", password="supersecret", onboarding_completed=True)
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


def test_upload_filename_cannot_escape_upload_dir(auth_client):
    """A crafted filename must not write outside the configured UPLOAD_DIR."""
    malicious = SimpleUploadedFile(
        "../../../../tmp/evil.wav", b"fakeaudio", content_type="audio/wav"
    )
    with patch("recipes.views.run_extraction_job.delay") as delay:
        auth_client.post(
            "/jobs/start/",
            {"source": "upload", "youtube_video_id": "abc", "title": "Pasta",
             "media": malicious},
        )
    written = Path(delay.call_args.kwargs["file_path"]).resolve()
    upload_dir = Path(settings.UPLOAD_DIR).resolve()
    assert upload_dir in written.parents
    assert written.suffix == ".wav"
    written.unlink(missing_ok=True)


def test_web_to_worker_file_handoff(auth_client):
    """The file written by start_job must be readable by run_extraction_job
    using only the path passed across the queue (no in-memory handle)."""
    user = User.objects.get(email="u@e.com")
    with patch("recipes.views.run_extraction_job.delay") as delay:
        auth_client.post(
            "/jobs/start/",
            {"source": "upload", "youtube_video_id": "abc", "title": "Pasta",
             "media": SimpleUploadedFile("a.wav", b"realbytes", content_type="audio/wav")},
        )
    job_id = delay.call_args.args[0]
    file_path = delay.call_args.kwargs["file_path"]
    assert Path(file_path).read_bytes() == b"realbytes"

    summary = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}
    with patch("recipes.tasks.ml_client.transcribe",
               return_value={"transcript": "t"}) as tr, \
         patch("recipes.tasks.ml_client.extract", return_value=summary):
        run_extraction_job(job_id, file_path=file_path)
    tr.assert_called_once()
    job = ExtractionJob.objects.get(pk=job_id)
    assert job.status == ExtractionJob.Status.DONE
    assert Recipe.objects.filter(owner=user, title="Pasta").exists()
    assert not Path(file_path).exists()  # cleaned up by the task
