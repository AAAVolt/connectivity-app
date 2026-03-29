"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://bizkaia:bizkaia_local@localhost:5432/bizkaia"
    )
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    environment: str = "local"

    model_config = {"env_prefix": "", "case_sensitive": False}


@lru_cache
def get_settings() -> Settings:
    return Settings()
