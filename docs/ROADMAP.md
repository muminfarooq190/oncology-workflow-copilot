# Weeks 5–12 execution roadmap

| Week | Deliverable | Exit condition |
|---|---|---|
| 5 | Product boundary, architecture, threat model, contracts, repository scaffold, CI, local stack, first golden case | One documented case passes repository and contract validation |
| 6 | .NET FHIR validation, reference resolution, canonical mapping, 25 cases | Field-level provenance and extraction benchmark are reproducible |
| 7 | Durable FastAPI state machine, PostgreSQL, Redis worker, append-only audit | Retry and idempotency integration tests pass |
| 8 | Evidence ingestion, hybrid retrieval, frozen corpus, 60 cases | Repeatable retrieval report meets interim recall target |
| 9 | Structured generation, citation verification, React review workflow, OIDC/RBAC | Clinician can review, correct, approve, and inspect provenance |
| 10 | Complete 100-case suite, adversarial coverage, evaluation dashboard | Baseline report and failure taxonomy are published |
| 11 | OpenTelemetry, hardening, Terraform, cloud deployment, Kubernetes portability | Deployed demo, telemetry, rollback, and security checks work |
| 12 | Locked test, launch decision, demo, runbook, handoff | Evidence-backed go/no-go decision and reproducible release |

## Work discipline

- Every week ends with an executable artifact and explicit exit test.
- Clinical correctness and evaluations take priority over infrastructure ornamentation.
- The locked test set is not inspected or tuned against before Week 12.
- Scope expansion beyond NSCLC requires a passed NSCLC launch review.

