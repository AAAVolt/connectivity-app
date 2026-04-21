"""Worker configuration via environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    data_dir: str = "/data"
    serving_dir: str = "/data/serving"
    gcs_bucket: str = "bizkaia-data-pub"
    gcs_prefix: str = "serving"
    environment: str = "local"

    model_config = {"env_prefix": "", "case_sensitive": False}


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
