import io
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_transcribe_returns_text():
    fake = {"transcript": "mix the flour", "language": "en", "duration": 12.0}
    with patch("app.main.transcribe_file", return_value=fake):
        resp = client.post(
            "/transcribe",
            files={"file": ("a.wav", io.BytesIO(b"RIFFfakeaudio"), "audio/wav")},
        )
    assert resp.status_code == 200
    assert resp.json() == fake


def test_transcribe_rejects_empty():
    resp = client.post(
        "/transcribe", files={"file": ("a.wav", io.BytesIO(b""), "audio/wav")}
    )
    assert resp.status_code == 400


def test_transcribe_rejects_too_long():
    with patch("app.main.probe_duration", return_value=99999.0), \
         patch("app.main.transcribe_file") as tr:
        resp = client.post(
            "/transcribe",
            files={"file": ("a.wav", io.BytesIO(b"RIFFfakeaudio"), "audio/wav")},
        )
    assert resp.status_code == 400
    assert "too long" in resp.json()["detail"]
    tr.assert_not_called()
