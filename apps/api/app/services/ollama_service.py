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
                 timeout: int | None = None, num_predict: int = 2000,
                 temperature: float = 0.0, retries: int | None = None,
                 client: httpx.Client | None = None) -> None:
        from app.config import settings

        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout if timeout is not None else \
            settings.ollama_timeout_seconds
        self.num_predict = num_predict
        self.temperature = temperature
        # One extra attempt absorbs transient queueing timeouts on a
        # shared Ollama; the repair loop above still owns JSON validity.
        self.retries = retries if retries is not None else \
            settings.ollama_retries
        self.client = client or httpx.Client(timeout=float(self.timeout))

    def chat_json(self, system: str, user: str) -> dict:
        """Chat turn with format=json. Retries once on transport timeout.

        A shared Ollama instance can make a request wait for another
        consumer's inference to drain; one extra attempt absorbs that.
        JSON validity stays with the caller's Pydantic repair loop.
        """
        last_error: Exception | None = None
        for attempt in range(max(self.retries, 0) + 1):
            try:
                return self._chat_once(system, user)
            except httpx.TimeoutException as e:
                last_error = e
                log.warning("ollama_timeout_retry", attempt=attempt,
                            model=self.model)
        raise OllamaError(f"ollama request failed after "
                         f"{max(self.retries, 0) + 1} attempts: "
                         f"{last_error}")

    def _chat_once(self, system: str, user: str) -> dict:
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
        except httpx.TimeoutException:
            # re-raise for chat_json's retry (HTTPError won't match first)
            raise
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
