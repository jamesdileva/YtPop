from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "YtPop API"
    version: str = "0.1.0"
    env: str = "dev"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    db_path: str = "data/database/mega_clipper.db"

    model_config = {"env_prefix": "YTPOP_"}


settings = Settings()
