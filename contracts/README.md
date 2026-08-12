# Shared contracts

These JSON Schemas are the versioned integration boundary between the web app, orchestrator, FHIR service, evaluation harness, and audit store.

- `canonical-oncology-case`: normalized patient-record facts with field-level FHIR provenance.
- `tumor-board-packet`: clinician-reviewable generated output with claim-level evidence.
- `audit-event`: minimum append-only event envelope.

Schemas use JSON Schema draft 2020-12. Contract changes require consumer tests and explicit versioning; do not silently mutate a released schema.

