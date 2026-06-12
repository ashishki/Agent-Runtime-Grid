from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_BIND_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(min_length=1, alias="DATABASE_URL")
    redis_url: str = Field(min_length=1, alias="REDIS_URL")
    artifact_root: str = Field(min_length=1, alias="ARTIFACT_ROOT")

    api_token: str | None = Field(default=None, alias="API_TOKEN")
    api_bind_host: str = Field(default="127.0.0.1", alias="API_BIND_HOST")
    llm_mode: str = Field(default="stub", alias="LLM_MODE")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    worker_concurrency: int = Field(default=1, alias="WORKER_CONCURRENCY", ge=1)
    job_default_timeout_seconds: int = Field(
        default=300,
        alias="JOB_DEFAULT_TIMEOUT_SECONDS",
        ge=1,
    )
    job_max_retries: int = Field(default=3, alias="JOB_MAX_RETRIES", ge=0)
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None,
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )
    prometheus_port: int | None = Field(default=None, alias="PROMETHEUS_PORT", ge=1)


def load_settings() -> Settings:
    return Settings()


def is_local_bind_host(host: str) -> bool:
    return host.strip().lower() in LOCAL_BIND_HOSTS


def validate_local_auth_boundary(*, api_token: str | None, api_bind_host: str) -> None:
    if api_token:
        return
    if not is_local_bind_host(api_bind_host):
        raise ValueError("API_TOKEN is required when API_BIND_HOST is not localhost")
