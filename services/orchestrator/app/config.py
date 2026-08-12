from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Oncology Workflow Copilot Orchestrator"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://oncology:oncology@localhost:5432/oncology"
    redis_url: str = "redis://localhost:6379/0"
    fhir_integration_url: str = "http://localhost:8081"
    evidence_corpus_version: str = "nsclc-v1"
    tenant_id: str = "portfolio"
    workflow_stream: str = "oncology:workflows"
    workflow_consumer_group: str = "orchestrator-workers"
    workflow_consumer_name: str = "worker-1"
    workflow_max_attempts: int = 3
    workflow_retry_delay_seconds: float = 5.0
    outbox_poll_interval_seconds: float = 0.5
    worker_poll_milliseconds: int = 5_000
    worker_claim_idle_milliseconds: int = 30_000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
