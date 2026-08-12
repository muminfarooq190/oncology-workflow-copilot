# Orchestrator

The FastAPI service owns workflow state, retrieval, generation, verification, escalation, and audit commands. It does not interpret raw FHIR beyond enforcing the synthetic-data boundary and envelope validation; canonicalization belongs to the .NET service.

Week 5 exposes health endpoints and an idempotent intake contract. PostgreSQL, Redis-backed execution, and durable state transitions arrive in Week 7.

