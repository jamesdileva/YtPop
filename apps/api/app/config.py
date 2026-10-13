import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# .env precedence: real environment > user-data .env > repo .env.
# Both files load with override=False in that priority order, so a file can
# never clobber a value set deliberately (the Electron shell exports an
# absolute YTPOP_DB_PATH; a copied repo .env carrying the dev-relative
# YTPOP_DB_PATH used to stomp it and 500 every DB endpoint in packaged runs).
def _load_file_env(data_env: Path, repo_env: Path) -> None:
    for candidate in (data_env, repo_env):
        if candidate.is_file():
            load_dotenv(candidate, override=False)


_DATA_ENV = Path(os.environ.get("YTPOP_DATA_DIR", "")) / ".env"
_REPO_ENV = Path(__file__).resolve().parents[4] / ".env"
_load_file_env(_DATA_ENV, _REPO_ENV)


class Settings(BaseSettings):
    app_name: str = "YtPop API"
    version: str = "0.1.0"
    env: str = "dev"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    db_path: str = "data/database/mega_clipper.db"
    youtube_api_key: str = ""
    youtube_quota_daily_budget: int = 10000
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    clip_embeddings: bool = True
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_editor_model: str = "qwen3.5:9b"
    # Shared/queued Ollama instances need headroom: requests wait for the
    # other consumer's inferences to drain (see runbook.md §7).
    ollama_timeout_seconds: int = 900
    ollama_retries: int = 1
    # Research/demo-only default: publishing stays blocked until a human
    # operator flips YTPOP_DEMO_MODE=false after review (S12).
    demo_mode: bool = True
    # S13 background scheduler (interval loop). Default off so tests and
    # one-shot runs stay deterministic; enable with YTPOP_SCHEDULER=true.
    scheduler: bool = False

    model_config = {"env_prefix": "YTPOP_"}


settings = Settings()
