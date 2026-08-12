from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Oncology Workflow Copilot Orchestrator"
    app_env: str = "development"
    log_level: str = "INFO"
    fhir_integration_url: str = "http://localhost:8081"
    evidence_corpus_version: str = "nsclc-v1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

