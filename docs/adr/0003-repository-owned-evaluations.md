# ADR 0003: Keep the evaluation harness in the repository

- Status: Accepted
- Date: 2026-08-12

## Context

The project needs reproducible comparisons across models and providers. Evaluation evidence must survive vendor-product changes and remain inspectable in CI.

## Decision

Cases, labels, scoring code, thresholds, manifests, and reports are versioned in this repository. Provider-hosted evaluation tools may be optional execution surfaces but are not the system of record.

## Consequences

- Results are portable and reviewable.
- Sensitive configuration stays outside fixtures and reports.
- The project must maintain its own dataset integrity and report schema.

