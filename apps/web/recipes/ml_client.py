import httpx
from django.conf import settings


def transcribe(file_bytes: bytes, filename: str) -> dict:
    resp = httpx.post(
        f"{settings.ML_SERVICE_URL}/transcribe",
        files={"file": (filename, file_bytes)},
        timeout=600,
    )
    resp.raise_for_status()
    return resp.json()


def extract(transcript: str, title: str | None) -> dict:
    resp = httpx.post(
        f"{settings.ML_SERVICE_URL}/extract",
        json={"transcript": transcript, "title": title},
        timeout=600,
    )
    resp.raise_for_status()
    return resp.json()
