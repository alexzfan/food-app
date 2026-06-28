import httpx
import pytest

from recipes import ml_client


def test_extract_surfaces_response_body_on_http_error(monkeypatch):
    # raise_for_status drops the response body, but the ML service puts the real
    # cause there (e.g. a 502 "Extraction failed: <...>"). The raised error must
    # carry it so it lands in job.error instead of a bare "502 Bad Gateway".
    request = httpx.Request("POST", "http://ml:8001/extract")
    response = httpx.Response(
        502,
        text="Extraction failed: Illegal header value b'Bearer '",
        request=request,
    )
    monkeypatch.setattr(ml_client.httpx, "post", lambda *a, **k: response)

    with pytest.raises(httpx.HTTPStatusError) as exc:
        ml_client.extract("boil pasta", "Pasta")

    assert "Illegal header value" in str(exc.value)


def test_extract_returns_json_on_success(monkeypatch):
    request = httpx.Request("POST", "http://ml:8001/extract")
    response = httpx.Response(200, json={"title": "Pasta"}, request=request)
    monkeypatch.setattr(ml_client.httpx, "post", lambda *a, **k: response)

    assert ml_client.extract("boil pasta", "Pasta") == {"title": "Pasta"}
