# FHIR integration service

This .NET 8 service is the sole raw-FHIR interpretation boundary. It uses the official Firely R4 SDK to parse and validate the core model, resolves in-bundle patient references, enforces the synthetic-data boundary, and maps supported NSCLC resources into canonical contract v1 with field-level provenance.

`POST /v1/fhir/validate` returns a structured validation result. `POST /v1/fhir/normalize` returns the validation result and, for valid input, the canonical case.

This phase does **not** claim conformance to a hospital-specific implementation guide. Profile validation requires a pinned IG package, terminology dependencies, and a resolver configuration specific to the target deployment.
