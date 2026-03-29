"""Worker configuration via environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg2://bizkaia:bizkaia_local@localhost:5432/bizkaia"
    )
    data_dir: str = "/data"
    environment: str = "local"

    model_config = {"env_prefix": "", "case_sensitive": False}


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
