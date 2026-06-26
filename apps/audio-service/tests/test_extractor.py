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


def test_extract_endpoint_uses_extractor():
    fake = {"title": "Pasta", "ingredients": [], "instructions": [], "tags": []}

    class Stub:
        def extract(self, transcript, title):
            return fake

    with patch("app.main.get_extractor", return_value=Stub()):
        resp = client.post("/extract", json={"transcript": "boil pasta", "title": "Pasta"})
    assert resp.status_code == 200
    assert resp.json() == fake
