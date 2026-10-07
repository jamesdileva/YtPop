from pydantic_settings import BaseSettings


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

    model_config = {"env_prefix": "YTPOP_"}


settings = Settings()
