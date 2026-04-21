"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings

_INSECURE_SECRETS = frozenset({
    "dev-secret-change-me",
    "CHANGE-ME-IN-PROD",
    "",
})


class Settings(BaseSettings):
    # Data source: "local" reads Parquet from data_dir, "gcs" downloads from GCS first.
    data_source: str = "local"
    data_dir: str = "./data/serving"
    gcs_bucket: str = "bizkaia-data-pub"
    gcs_prefix: str = "serving"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    environment: str = "local"
    cors_origins: str = "http://localhost:3000"
    cors_origin_regex: str = r"https://.*\.(run\.app|vercel\.app)"

    model_config = {"env_prefix": "", "case_sensitive": False}

    @model_validator(mode="after")
    def _check_jwt_secret(self) -> "Settings":
        if self.environment != "local" and self.jwt_secret in _INSECURE_SECRETS:
            raise ValueError(
                "JWT_SECRET must be set to a strong, unique value in "
                f"non-local environments (current environment: {self.environment})"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
