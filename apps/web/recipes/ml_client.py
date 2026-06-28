import httpx
from django.conf import settings


def _raise_for_status(resp: httpx.Response) -> None:
    """Like resp.raise_for_status(), but keep the response body in the error.

    The ML service returns the real failure cause in the body (e.g. a 502
    "Extraction failed: <...>"); httpx's default error drops it, which is how
    these failures became undiagnosable in job.error.
    """
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        body = resp.text.strip()
        if body:
            raise httpx.HTTPStatusError(
                f"{e} -- {body}", request=e.request, response=e.response
            ) from e
        raise


def transcribe(file_bytes: bytes, filename: str) -> dict:
    resp = httpx.post(
        f"{settings.ML_SERVICE_URL}/transcribe",
        files={"file": (filename, file_bytes)},
        timeout=600,
    )
    _raise_for_status(resp)
    return resp.json()


def extract(transcript: str, title: str | None) -> dict:
    resp = httpx.post(
        f"{settings.ML_SERVICE_URL}/extract",
        json={"transcript": transcript, "title": title},
        timeout=600,
    )
    _raise_for_status(resp)
    return resp.json()
