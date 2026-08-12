# Security and privacy design

## Boundary

This public repository and its demo environments accept synthetic data only. The architecture demonstrates controls expected in regulated delivery, but it is not a compliance certification and is not authorized for PHI.

## Protected assets

- Synthetic clinical records and derived packets.
- Identity, role, session, and authorization information.
- Model-provider and infrastructure credentials.
- Evidence corpus integrity and versions.
- Audit events, clinician corrections, and evaluation results.

## Principal threats and controls

| Threat | Control |
|---|---|
| Unauthorized case access | OIDC, server-side RBAC, case-level authorization checks, deny by default |
| Prompt injection in clinical notes | Treat records as data, schema-constrained stages, tool allowlists, adversarial evals |
| Unsupported clinical claims | Claim-level provenance, citation verification, abstention and escalation |
| Evidence poisoning or silent updates | Allowlisted sources, immutable manifests, content hashes, corpus versions |
| Secret or patient data in logs | Structured allowlist logging, synthetic IDs, log-redaction tests |
| Audit tampering | Append-only events, actor and correlation IDs, chained event hashes in later phase |
| Cross-tenant leakage | Tenant keys in authorization and persistence queries; negative integration tests |
| Dependency compromise | Lockfiles, dependency scanning, minimal images, signed release artifacts in later phase |
| Retry duplication | Idempotency keys, unique constraints, monotonic workflow transitions |
| Model/provider outage | Timeouts, bounded retries, circuit breaker, failed-safe escalation |

## Roles

| Role | Capabilities |
|---|---|
| Coordinator | Create case, view workflow status, resolve non-clinical validation errors |
| Clinician | Review, correct, approve, or escalate assigned cases |
| Evaluator | View synthetic eval inputs/outputs and adjudicate labels |
| Auditor | Read audit and version metadata; cannot alter clinical content |
| Administrator | Manage access and configuration; cannot approve as clinician by default |

## Audit minimum

Each event records event ID, UTC timestamp, actor, role, action, workflow and tenant IDs, correlation/trace ID, prior and next state, input/output hashes, contract version, corpus version, model and prompt versions, and reason metadata. Sensitive raw payloads are stored separately and are never placed directly in logs.

## Retention and deletion

The portfolio default is short-lived synthetic runtime data. A real deployment would require customer-specific retention, legal hold, deletion, residency, backup, and disaster-recovery requirements before launch.

