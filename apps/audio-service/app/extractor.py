import json
import os
import re

import httpx

from .prompt import build_prompt


def parse_recipe_response(text: str) -> dict:
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
    if fence:
        s = fence.group(1)
    obj = re.search(r"\{[\s\S]*\}", s)
    if obj:
        s = obj.group(0)
    recipe = json.loads(s)
    if not recipe.get("title"):
        raise ValueError("Missing required field: title")
    recipe.setdefault("ingredients", [])
    recipe.setdefault("instructions", [])
    recipe.setdefault("tags", [])
    return recipe


class LocalGemmaExtractor:
    """Calls a local Ollama server running Gemma 3n."""

    def __init__(self):
        self.url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.model = os.environ.get("GEMMA_MODEL", "gemma4:26b-a4b-it-qat")

    def extract(self, transcript: str, title: str | None) -> dict:
        prompt = build_prompt(transcript, title)
        resp = httpx.post(
            f"{self.url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=180,
        )
        resp.raise_for_status()
        return parse_recipe_response(resp.json()["response"])


class HostedExtractor:
    """Calls a hosted LLM API (OpenAI-compatible chat completions)."""

    def __init__(self):
        self.url = os.environ.get("HOSTED_LLM_URL", "")
        self.api_key = os.environ.get("HOSTED_LLM_API_KEY", "")
        self.model = os.environ.get("HOSTED_LLM_MODEL", "")

    def extract(self, transcript: str, title: str | None) -> dict:
        prompt = build_prompt(transcript, title)
        resp = httpx.post(
            self.url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=180,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return parse_recipe_response(content)


def get_extractor():
    backend = os.environ.get("EXTRACTOR_BACKEND", "local").lower()
    return HostedExtractor() if backend == "hosted" else LocalGemmaExtractor()
