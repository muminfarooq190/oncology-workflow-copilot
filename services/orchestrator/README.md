# Orchestrator

The FastAPI service owns workflow state, retrieval, generation, verification, escalation, and audit commands. It does not interpret raw FHIR beyond enforcing the synthetic-data boundary and envelope validation; canonicalization belongs to the .NET service.

Week 7 implements durable workflow intake and FHIR-normalization execution:

- PostgreSQL stores the workflow state, raw synthetic bundle, retry budget, and ordered audit events.
- A unique tenant/idempotency-key constraint returns the original workflow for an identical replay and rejects a changed payload with `409`.
- A transactional outbox prevents the database/queue dual-write gap.
- Redis Streams consumer groups deliver normalization work; terminal-state and outbox-ID checks make redelivery safe.
- Transient failures use bounded exponential retries and finish in `dead_letter`; an explicit API command can requeue them.
- A PostgreSQL trigger rejects `UPDATE` and `DELETE` against audit events.

Week 8 adds frozen evidence ingestion and hybrid retrieval:

- A manifest and per-chunk SHA-256 checks make the `nsclc-v1` snapshot reproducible.
- Idempotent ingestion rejects immutable-version conflicts.
- PostgreSQL English full-text search and pgvector cosine ranking produce independent candidates.
- Reciprocal-rank fusion combines the lists while retaining both component ranks.
- Search responses include the source URL, date, locator, content hash, and corpus/model versions.

## Processes

The same image runs five independent commands:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
python -m app.outbox
python -m app.worker
alembic upgrade head
python -m app.evidence_ingest /app/evidence/manifest.json
```

Run the migration and evidence-ingestion commands before starting the API. Docker Compose handles this ordering.

## API

- `POST /v1/workflows` — idempotent synthetic-bundle intake.
- `GET /v1/workflows/{workflow_id}` — durable status and normalization result.
- `GET /v1/workflows/{workflow_id}/audit` — ordered append-only history.
- `POST /v1/workflows/{workflow_id}/retry` — explicit dead-letter recovery.
- `POST /v1/evidence/search` — versioned hybrid evidence search with reviewable provenance.
- `GET /health/live` — process health only.
- `GET /health/ready` — PostgreSQL, Redis, and FHIR integration probes.
