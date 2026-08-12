# ADR 0001: Limit the first release to NSCLC

- Status: Accepted
- Date: 2026-08-12

## Context

Oncology requirements vary materially by disease. A pan-tumor prototype would either encode shallow rules or create a clinically unreviewable gold dataset within eight weeks.

## Decision

The first release supports adult synthetic NSCLC tumor-board preparation only. Unsupported cancers are rejected with an explicit `unsupported_scope` escalation.

## Consequences

- Evaluation labels can be clinically specific and adjudicated.
- Evidence metadata and completeness rules remain manageable.
- The architecture must still allow future disease modules without weakening existing contracts.

