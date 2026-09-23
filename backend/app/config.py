from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    database_url: str = "postgresql+asyncpg://tracker:tracker@db:5432/findhub"
    auth_secrets_path: str = "/app/auth/secrets.json"
    poll_interval_min: int = 15
    api_token: str = ""
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()