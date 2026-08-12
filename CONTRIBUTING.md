# Contributing

## Non-negotiable rules

- Use only synthetic or properly licensed public data.
- Never commit PHI, credentials, access tokens, or proprietary guideline text.
- Preserve claim-level provenance through every transformation.
- Any clinical-output change must add or update evaluation cases.
- Any contract change must be versioned and remain backward compatible or include an explicit migration.
- Generated text must remain a clinician-reviewable draft; do not bypass approval or escalation.

## Pull-request expectations

Every pull request should state:

1. Which workflow problem it solves.
2. Which contracts or clinical assumptions changed.
3. Which automated and evaluation checks were run.
4. Any new failure mode or residual risk.
5. Whether the change affects launch criteria.

## Branches and commits

- Branches: `feature/<description>`, `fix/<description>`, or `agent/<description>`.
- Keep commits scoped and explain why the change exists.
- Prefer a draft pull request while evaluation evidence is incomplete.

## Definition of done

A change is done only when code, contracts, tests, documentation, telemetry, and relevant evaluation cases agree. A successful demo is not evidence of production readiness.

