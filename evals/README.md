# Evaluation suite

Each case directory contains a case manifest, a synthetic FHIR input reference, and gold labels. Development cases may evolve. Validation labels are changed only through an adjudication change record. Locked-test labels remain unavailable to prompt and retrieval tuning until launch review.

Week 6 contains 25 deterministic development cases spanning complete, incomplete, contradictory, rare, and invalid-FHIR scenarios. The engineering labels are explicitly marked `clinicianAdjudication.status: pending`; they must not be promoted to validation or locked-test partitions until a clinician adjudicates them. Evidence labels intentionally remain empty until the `nsclc-v1` corpus is frozen.

Regenerate the suite and validate its manifests:

```bash
make generate-week6
make validate-contracts
```

The extraction scorer accepts one JSON prediction per case. A prediction can be either the `/v1/fhir/normalize` response or the canonical case itself:

```bash
python -m evals.scorers.extraction evals/predictions \
  --output evals/reports/extraction.json
```

It reports structural-validation accuracy, micro-averaged required-field precision/recall/F1, exact field provenance, missing-information exact match, and contradiction exact match. Missing predictions fail instead of being silently excluded.
