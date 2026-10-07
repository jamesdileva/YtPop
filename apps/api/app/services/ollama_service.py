"""Ollama adapter (S10): chat with forced JSON output.

Role→model mapping lives in configs/default.yaml (models.*); this module
only transports prompts and parses JSON. Never trust raw model output —
callers validate with Pydantic.
"""

import structlog
import httpx

log = structlog.get_logger()


def parse_json_content(content: str) -> dict:
    """Strict-parse model output, tolerating <think> preamble/postamble."""
    import json as _json
    import re

    text = content.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    try:
        return _json.loads(text)
    except ValueError:
        pass
    # last resort: largest {...} block (still Pydantic-validated by caller)
    matches = re.findall(r"\{.*\}", text, flags=re.DOTALL)
    for candidate in sorted(matches, key=len, reverse=True):
        try:
            return _json.loads(candidate)
        except ValueError:
            continue
    raise ValueError(f"no JSON object found in {len(content)} chars")


class OllamaError(RuntimeError):
    pass


class OllamaService:
    def __init__(self, model: str, host: str = "http://127.0.0.1:11434",
                 timeout: int = 300, num_predict: int = 2000,
                 temperature: float = 0.0,
                 client: httpx.Client | None = None) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.num_predict = num_predict
        self.temperature = temperature
        self.client = client or httpx.Client(timeout=float(timeout))

    def chat_json(self, system: str, user: str) -> dict:
        """Single chat turn with format=json. Returns parsed object."""
        try:
            resp = self.client.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "format": "json",
                    "stream": False,
                    "think": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.num_predict,
                    },
                },
            )
        except httpx.HTTPError as e:
            raise OllamaError(f"ollama request failed: {e}") from e
        if resp.status_code != 200:
            raise OllamaError(
                f"ollama api error {resp.status_code}: {resp.text[:300]}")
        try:
            content = resp.json()["message"]["content"]
            return parse_json_content(content)
        except (KeyError, ValueError, TypeError) as e:
            raise OllamaError(f"ollama returned non-JSON: {e}") from e

    def ping(self) -> bool:
        try:
            r = self.client.get(f"{self.host}/api/tags",
                                timeout=5.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False


def model_for(role: str, models_cfg: dict | None = None) -> str:
    """Role→model routing (cheap-first ladder)."""
    from app.config import settings

    defaults = {"classifier": "qwen3:4b", "summarizer": "qwen3:4b",
                "editor": settings.ollama_editor_model,
                "vision": "qwen2.5vl:3b"}
    if models_cfg:
        defaults.update(models_cfg)
    if role not in defaults:
        raise OllamaError(f"unknown model role {role!r}")
    return defaults[role]
