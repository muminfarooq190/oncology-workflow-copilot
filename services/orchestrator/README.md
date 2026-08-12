# Orchestrator

The FastAPI service owns workflow state, retrieval, generation, verification, escalation, and audit commands. It does not interpret raw FHIR beyond enforcing the synthetic-data boundary and envelope validation; canonicalization belongs to the .NET service.

Week 7 implements durable workflow intake and FHIR-normalization execution:

- PostgreSQL stores the workflow state, raw synthetic bundle, retry budget, and ordered audit events.
- A unique tenant/idempotency-key constraint returns the original workflow for an identical replay and rejects a changed payload with `409`.
- A transactional outbox prevents the database/queue dual-write gap.
- Redis Streams consumer groups deliver normalization work; terminal-state and outbox-ID checks make redelivery safe.
- Transient failures use bounded exponential retries and finish in `dead_letter`; an explicit API command can requeue them.
- A PostgreSQL trigger rejects `UPDATE` and `DELETE` against audit events.

## Processes

The same image runs three independent processes:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
python -m app.outbox
python -m app.worker
```

Run `alembic upgrade head` before starting them. Docker Compose handles migration ordering and process startup.

## API

- `POST /v1/workflows` — idempotent synthetic-bundle intake.
- `GET /v1/workflows/{workflow_id}` — durable status and normalization result.
- `GET /v1/workflows/{workflow_id}/audit` — ordered append-only history.
- `POST /v1/workflows/{workflow_id}/retry` — explicit dead-letter recovery.
- `GET /health/live` — process health only.
- `GET /health/ready` — PostgreSQL, Redis, and FHIR integration probes.
