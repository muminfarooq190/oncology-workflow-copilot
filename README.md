# Oncology Workflow Copilot

[![CI](https://github.com/muminfarooq190/oncology-workflow-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/muminfarooq190/oncology-workflow-copilot/actions/workflows/ci.yml)

An evaluation-first, clinician-reviewed workflow for converting **synthetic FHIR R4 oncology records** into an auditable tumor-board preparation packet.

This is a healthcare forward-deployed-engineering portfolio project, not a generic medical chatbot. The initial clinical scope is non-small-cell lung cancer (NSCLC). It demonstrates interoperability, regulated-system design, evidence retrieval, human review, evaluations, observability, and production handoff.

> **Safety boundary:** This repository uses synthetic data only. It does not diagnose, prescribe, replace clinical judgment, or claim HIPAA compliance. Generated packets are drafts that require an authorized clinician's review and approval.

## Target workflow

1. Accept a synthetic FHIR R4 `Bundle`.
2. Validate and normalize it into a versioned canonical oncology case.
3. identify missing or contradictory clinical information.
4. Retrieve evidence from a frozen, versioned corpus.
5. Generate a schema-constrained tumor-board preparation packet.
6. Verify claim-level citations and escalate unsafe or uncertain cases.
7. Capture clinician corrections, approval, provenance, latency, and cost.

```mermaid
flowchart TD
    A["Synthetic FHIR bundle"] --> B["FastAPI workflow API"]
    B --> C[".NET FHIR boundary"]
    C --> D["Canonical oncology case"]
    D --> E["Queued workflow"]
    E --> F["Versioned evidence retrieval"]
    E --> G["Structured generation"]
    F --> H["Cited draft packet"]
    G --> H
    H --> I["Clinician review"]
    I --> J["Audit and evaluations"]
```

## Repository map

| Path | Purpose |
|---|---|
| `apps/web` | React/TypeScript clinician review interface |
| `services/orchestrator` | FastAPI workflow orchestration and evaluation hooks |
| `services/fhir-integration` | .NET 8 FHIR validation and canonicalization boundary |
| `contracts` | Versioned JSON contracts shared across services |
| `data/synthetic-fhir` | Synthetic FHIR R4 inputs only |
| `evidence` | Frozen, content-addressed public-source evidence corpus and ingestion manifest |
| `evals` | Cases, gold labels, scorers, and generated reports |
| `infra` | Local Docker, Terraform, and Kubernetes assets as the project matures |
| `docs` | Product, architecture, safety, evaluation, and operating decisions |

## Quick start

Prerequisites: Node.js 22+, Python 3.12+, .NET 8 SDK, Docker with Compose.

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD and KEYCLOAK_ADMIN_PASSWORD in .env before continuing.
make install
make test
docker compose up --build
```

Local endpoints after the complete stack starts:

- Web UI: `http://localhost:5173`
- Orchestrator API: `http://localhost:8000/docs`
- FHIR integration service: `http://localhost:8081/health`
- Keycloak: `http://localhost:8082`

## Delivery plan

The implementation is deliberately staged. See [the execution roadmap](docs/ROADMAP.md), [launch criteria](docs/LAUNCH_CRITERIA.md), and [evaluation plan](docs/EVALUATION_PLAN.md). A feature is not considered complete because the output “looks good”; it must pass deterministic tests and the relevant clinical evaluation threshold.

## Current status

**Week 8 — evidence retrieval:** a frozen 19-chunk NSCLC corpus of original paraphrases linked to NCI/FDA sources, hash-verified idempotent ingestion, PostgreSQL full-text search plus pgvector cosine retrieval, reciprocal-rank fusion, reviewable source metadata, and a 60-case development suite. The checked-in reference report reaches recall@5 of 1.00 across 55 retrieval-eligible cases; all labels still require clinical adjudication.

## Contribution rules

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Never add real patient data, credentials, paid guideline text, or screenshots containing protected information.
