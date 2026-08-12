# ADR 0002: Own FHIR normalization in the .NET service

- Status: Accepted
- Date: 2026-08-12

## Context

Allowing multiple services to interpret raw FHIR would duplicate clinical mappings and make provenance, testing, and contract changes inconsistent.

## Decision

The .NET 8 integration service is the only component that interprets raw FHIR. It validates bundles, resolves references, normalizes supported terminology, and emits canonical oncology case contract v1 with field-level provenance.

## Consequences

- Python orchestration stays independent of FHIR-library details.
- Mapping behavior can be tested deterministically.
- The .NET service is a meaningful interoperability boundary rather than a decorative microservice.

