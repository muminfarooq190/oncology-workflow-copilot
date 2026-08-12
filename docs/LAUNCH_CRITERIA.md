# Launch criteria

## Decision rule

The hosted portfolio demo may be labelled **evaluation-qualified** only when all blocking gates pass on the locked test partition. It must never be labelled clinically validated, HIPAA compliant, or suitable for patient care.

## Blocking gates

- [ ] Zero real patient records or PHI in code, history, logs, traces, screenshots, or test artifacts.
- [ ] Critical-field exact accuracy >= 98%.
- [ ] Required-field extraction F1 >= 95%.
- [ ] Retrieval recall@5 >= 90%.
- [ ] Citation support >= 95%.
- [ ] Unsupported material clinical-claim rate <= 2%.
- [ ] Mandatory-escalation sensitivity = 100%.
- [ ] Zero severity-5 unsafe errors on the locked set.
- [ ] Clinician approval is enforced server-side.
- [ ] Audit record contains all required versions and hashes.
- [ ] Backup, restore, rollback, and provider-failure runbooks are exercised in the demo environment.
- [ ] Critical and high security findings are resolved or explicitly accepted with documented rationale.

## Operating targets

- End-to-end p95 latency below 45 seconds.
- Initial model/embedding cost at or below USD 0.25 per completed case.
- Severity-weighted clinician correction rate at or below 15%.
- Escalation precision at or above 80%, reported by category.

Failure of an operating target blocks promotion unless an architecture decision documents why the target was invalid and establishes a replacement before viewing locked-test results.

## Required release evidence

- Immutable source commit and container digests.
- Versioned evaluation report with dataset manifest and environment.
- Error analysis for every failed case.
- Model, prompt, contract, and corpus versions.
- Threat-model review and dependency scan.
- Observability screenshots containing synthetic identifiers only.
- Rollback and handoff checklist.

