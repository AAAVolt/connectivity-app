"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings

_INSECURE_SECRETS = frozenset({
    "dev-secret-change-me",
    "CHANGE-ME-IN-PROD",
    "",
})

# Explicit allow-list of environment names. Anything outside this set (typos
# like "prod", "Production", "dev") is rejected at startup so a misconfigured
# deployment fails loudly instead of silently disabling auth.
_VALID_ENVIRONMENTS = frozenset({
    "local",
    "test",
    "development",
    "staging",
    "production",
})

# Environments where the insecure default JWT secret is tolerated.
_LOCAL_ENVIRONMENTS = frozenset({"local", "test"})


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
    cors_origin_regex: str = (
        r"^https://("
        r"bizkaia-api-[a-z0-9-]+\.a\.run\.app"
        r"|frontend-[a-z0-9-]+\.vercel\.app"
        r"|[a-z0-9-]+-alessandrovoltan-4656s-projects\.vercel\.app"
        r")$"
    )

    model_config = {"env_prefix": "", "case_sensitive": False}

    @model_validator(mode="after")
    def _validate_security(self) -> "Settings":
        env = self.environment.strip()
        if env not in _VALID_ENVIRONMENTS:
            raise ValueError(
                f"ENVIRONMENT must be one of {sorted(_VALID_ENVIRONMENTS)}, "
                f"got: {self.environment!r}"
            )
        if env not in _LOCAL_ENVIRONMENTS and self.jwt_secret in _INSECURE_SECRETS:
            raise ValueError(
                "JWT_SECRET must be set to a strong, unique value in "
                f"non-local environments (current environment: {env})"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
