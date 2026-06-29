import json
import os
import re

import httpx

from .prompt import build_prompt


def _coerce_start(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


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
    for step in recipe["instructions"]:
        if isinstance(step, dict):
            step["start"] = _coerce_start(step.get("start"))
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
        # Only send Authorization when we actually have a key. An empty key
        # yields "Bearer ", whose trailing space h11 rejects at send time
        # ("Illegal header value") — which is how the local llama.cpp backend
        # (no api key) failed before the request ever left the service.
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        resp = httpx.post(
            self.url,
            headers=headers,
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=180,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return parse_recipe_response(content)


class LlamaCppExtractor(HostedExtractor):
    """A local llama.cpp server (OpenAI-compatible).

    Used for GPU serving of large MoE models with expert offload (e.g. Gemma 4
    26B-A4B with `-ngl 99 -ot exps=CPU`). Reuses HostedExtractor's OpenAI chat
    call; llama.cpp ignores the api key and model fields for a single loaded
    model.
    """

    def __init__(self):
        self.url = os.environ.get(
            "LLAMACPP_URL", "http://llamacpp:8080/v1/chat/completions"
        )
        self.api_key = os.environ.get("LLAMACPP_API_KEY", "")
        self.model = os.environ.get("LLAMACPP_MODEL", "gemma")


def get_extractor():
    backend = os.environ.get("EXTRACTOR_BACKEND", "local").lower()
    if backend == "hosted":
        return HostedExtractor()
    if backend == "llamacpp":
        return LlamaCppExtractor()
    return LocalGemmaExtractor()
