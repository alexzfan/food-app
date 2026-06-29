from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.extractor import parse_recipe_response
from app.main import app

client = TestClient(app)


def test_parse_strips_markdown_fence():
    raw = '```json\n{"title": "Soup", "ingredients": [], "instructions": []}\n```'
    assert parse_recipe_response(raw)["title"] == "Soup"


def test_parse_extracts_object_amid_prose():
    raw = 'Here you go: {"title": "Soup"} hope it helps'
    out = parse_recipe_response(raw)
    assert out["title"] == "Soup"
    assert out["ingredients"] == []  # defaulted


def test_parse_requires_title():
    with pytest.raises(ValueError):
        parse_recipe_response('{"description": "x"}')


def test_parse_reports_clear_error_when_no_json_object():
    # A prose-only / truncated response must not surface as the cryptic
    # "Expecting value: line 1 column 1 (char 0)" JSONDecodeError. The error
    # should say the model returned no JSON and include a snippet to diagnose.
    with pytest.raises(ValueError) as exc:
        parse_recipe_response("Sure! Here is the recipe you asked for")
    msg = str(exc.value)
    assert "JSON" in msg
    assert "Sure!" in msg  # snippet of what actually came back


def test_parse_reports_empty_response():
    with pytest.raises(ValueError) as exc:
        parse_recipe_response("   ")
    assert "empty" in str(exc.value).lower()


def test_parse_reports_malformed_truncated_json():
    # Output cut off mid-object: clear "malformed JSON" message, not a raw
    # "Unterminated string" / "Expecting ',' delimiter".
    with pytest.raises(ValueError) as exc:
        parse_recipe_response('{"title": "Pas')
    assert "JSON" in str(exc.value)


def test_get_extractor_selects_backend(monkeypatch):
    from app.extractor import (
        HostedExtractor,
        LlamaCppExtractor,
        LocalGemmaExtractor,
        get_extractor,
    )

    monkeypatch.setenv("EXTRACTOR_BACKEND", "llamacpp")
    assert isinstance(get_extractor(), LlamaCppExtractor)
    monkeypatch.setenv("EXTRACTOR_BACKEND", "hosted")
    assert isinstance(get_extractor(), HostedExtractor)
    monkeypatch.setenv("EXTRACTOR_BACKEND", "local")
    assert isinstance(get_extractor(), LocalGemmaExtractor)


class _FakeResp:
    def __init__(self, content='{"title": "Pasta"}'):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_llamacpp_extractor_omits_auth_header_when_no_key(monkeypatch):
    # An empty LLAMACPP_API_KEY must NOT produce "Authorization: Bearer " — the
    # trailing-space value is rejected by h11 at send time (LocalProtocolError:
    # Illegal header value b'Bearer '), which surfaced as a 502 from /extract
    # before any request ever reached llama.cpp.
    from app.extractor import LlamaCppExtractor

    monkeypatch.delenv("LLAMACPP_API_KEY", raising=False)
    captured = {}
    monkeypatch.setattr(
        "app.extractor.httpx.post",
        lambda url, **kwargs: captured.update(kwargs) or _FakeResp(),
    )

    LlamaCppExtractor().extract("boil pasta", "Pasta")

    assert "Authorization" not in captured["headers"]


def test_hosted_extractor_flags_truncated_response(monkeypatch):
    # When the model hits the context/token limit, llama.cpp returns
    # finish_reason="length" with a cut-off body. That must raise a clear,
    # actionable error -- not an opaque JSONDecodeError surfaced as a 502.
    from app.extractor import HostedExtractor

    class _Trunc:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": '{"title": "Pas'},
                    }
                ]
            }

    monkeypatch.setattr("app.extractor.httpx.post", lambda url, **kwargs: _Trunc())

    with pytest.raises(ValueError) as exc:
        HostedExtractor().extract("a very long transcript", "Pasta")
    msg = str(exc.value).lower()
    assert "truncat" in msg
    assert "context" in msg or "transcript" in msg


def test_hosted_extractor_sends_auth_header_when_key_set(monkeypatch):
    from app.extractor import HostedExtractor

    monkeypatch.setenv("HOSTED_LLM_API_KEY", "sk-real")
    captured = {}
    monkeypatch.setattr(
        "app.extractor.httpx.post",
        lambda url, **kwargs: captured.update(kwargs) or _FakeResp(),
    )

    HostedExtractor().extract("boil pasta", "Pasta")

    assert captured["headers"]["Authorization"] == "Bearer sk-real"


def test_extract_endpoint_uses_extractor():
    fake = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}

    class Stub:
        def extract(self, transcript, title):
            return fake

    with patch("app.main.get_extractor", return_value=Stub()):
        resp = client.post("/extract", json={"transcript": "boil pasta", "title": "Pasta"})
    assert resp.status_code == 200
    assert resp.json() == fake


def test_prompt_advertises_start_field():
    from app.prompt import RECIPE_EXTRACTION_PROMPT, build_prompt

    assert '"start"' in RECIPE_EXTRACTION_PROMPT
    assert "start" in build_prompt("[0] boil", None)


def test_parse_coerces_instruction_start():
    raw = (
        '{"title": "Noodles", "instructions": ['
        '{"step": 1, "text": "a", "start": "12"},'
        '{"step": 2, "text": "b", "start": 13.9},'
        '{"step": 3, "text": "c", "start": "nope"},'
        '{"step": 4, "text": "d"}]}'
    )
    starts = [s.get("start") for s in parse_recipe_response(raw)["instructions"]]
    assert starts == [12, 13, None, None]


def test_parse_coerces_mmss_start():
    # LLMs frequently emit clock strings instead of integer seconds.
    raw = (
        '{"title": "Noodles", "instructions": ['
        '{"step": 1, "text": "a", "start": "1:30"},'
        '{"step": 2, "text": "b", "start": "1:02:03"}]}'
    )
    starts = [s.get("start") for s in parse_recipe_response(raw)["instructions"]]
    assert starts == [90, 3723]


def test_extract_endpoint_logs_cause_on_failure(caplog):
    # The 502 must not be a black box: the underlying cause is logged
    # server-side (with traceback) so ml logs are diagnosable, and is also
    # returned in the response detail.
    import logging

    class Boom:
        def extract(self, transcript, title):
            raise RuntimeError("llamacpp connection refused")

    with patch("app.main.get_extractor", return_value=Boom()):
        with caplog.at_level(logging.ERROR):
            resp = client.post("/extract", json={"transcript": "x"})

    assert resp.status_code == 502
    assert "llamacpp connection refused" in resp.json()["detail"]
    assert any(
        "extract failed" in r.getMessage() and r.exc_info for r in caplog.records
    )
