"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Data source: "local" reads Parquet from data_dir, "gcs" downloads from GCS first.
    data_source: str = "local"
    data_dir: str = "./data/serving"
    gcs_bucket: str = "bizkaia-conn-data"
    gcs_prefix: str = "serving"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    environment: str = "local"

    model_config = {"env_prefix": "", "case_sensitive": False}


@lru_cache
def get_settings() -> Settings:
    return Settings()
