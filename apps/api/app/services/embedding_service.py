"""Embedding backends (D7): local MiniLM, else Ollama, else keyword-only.

Whisper/ctranslate2 freeze cleanly; sentence-transformers pulls torch, which
would roughly triple a packaged install. So the embedder is resolved at
runtime: MiniLM when it imports, otherwise Ollama's `nomic-embed-text`
(local, cheap-first), otherwise None (clustering runs keyword-only).
"""

import math
import structlog

log = structlog.get_logger()


class LocalMiniLM:
    """sentence-transformers all-MiniLM-L6-v2 (L2-normalized)."""

    MODEL = "all-MiniLM-L6-v2"

    def __init__(self, model_name: str = MODEL) -> None:
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            log.info("embedder_load", model=self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        import numpy as np

        vecs = self.model.encode(texts, normalize_embeddings=True)
        return [list(map(float, v)) for v in np.asarray(vecs)]


class OllamaEmbedder:
    """Ollama /api/embed fallback (any locally pulled embedding model)."""

    def __init__(self, model: str = "nomic-embed-text",
                 host: str | None = None, client=None) -> None:
        self.model = model
        self.host = host
        self._client = client

    def _http(self):
        if self._client is not None:
            return self._client
        import httpx

        timeout = None
        try:
            from app.config import settings

            timeout = float(settings.ollama_timeout_seconds)
        except Exception:
            timeout = 120.0
        self._client = httpx.Client(timeout=timeout)
        return self._client

    def _base(self) -> str:
        if self.host:
            return self.host.rstrip("/")
        from app.config import settings

        return settings.ollama_host.rstrip("/")

    def encode(self, texts: list[str]) -> list[list[float]]:
        resp = self._http().post(
            f"{self._base()}/api/embed",
            json={"model": self.model, "input": texts},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"ollama embed error {resp.status_code}: {resp.text[:200]}")
        vecs = resp.json().get("embeddings") or []
        if len(vecs) != len(texts):
            raise RuntimeError(
                f"ollama returned {len(vecs)}/{len(texts)} embeddings")
        # normalize here so cosine math is identical to the MiniLM path
        out = []
        for v in vecs:
            n = math.sqrt(sum(float(x) * float(x) for x in v)) or 1.0
            out.append([float(x) / n for x in v])
        return out


def local_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401

        return True
    except Exception:
        return False


def ollama_available() -> bool:
    try:
        import httpx

        from app.config import settings

        resp = httpx.get(
            f"{settings.ollama_host.rstrip('/')}/api/tags", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


def resolve_embedder(backend: str = "auto"):
    """Return an object with .encode(texts) or None (keyword-only fallback)."""
    backends = {
        "minilm": (LocalMiniLM,),
        "ollama": (OllamaEmbedder,),
    }[backend] if backend in ("minilm", "ollama") else (
        LocalMiniLM, OllamaEmbedder)
    for cls in backends:
        if cls is LocalMiniLM and not local_available():
            continue
        if cls is OllamaEmbedder and not ollama_available():
            continue
        try:
            return cls()
        except Exception as e:
            log.info("embedder_unavailable", backend=cls.__name__,
                     error=str(e)[:200])
    log.warning("embedder_none", reason="no backend available - "
                                       "keyword-only scoring")
    return None
