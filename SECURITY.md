# Security policy

This is a synthetic-data portfolio project and is not authorized to process real patient data.

## Reporting

Do not open a public issue for a vulnerability. Contact the repository owner privately through their GitHub profile and provide reproduction steps without including secrets or patient information.

## Data handling

- Only synthetic patient bundles are permitted.
- Secrets must be injected at runtime and must never be committed.
- Logs and traces must use internal synthetic case identifiers rather than patient attributes.
- Evidence documents must be public-domain, openly licensed, or represented only by metadata and links.

The detailed threat model is in [`docs/SECURITY.md`](docs/SECURITY.md).

