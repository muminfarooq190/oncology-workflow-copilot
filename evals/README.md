# Evaluation suite

Each case directory contains a case manifest, a synthetic FHIR input reference, and gold labels. Development cases may evolve. Validation labels are changed only through an adjudication change record. Locked-test labels remain unavailable to prompt and retrieval tuning until launch review.

Week 8 contains 60 deterministic development cases spanning complete, incomplete, contradictory, rare, adversarial-record-content, and invalid-FHIR scenarios. The engineering labels are explicitly marked `clinicianAdjudication.status: pending`; they must not be promoted to validation or locked-test partitions until a clinician adjudicates them. Fifty-five valid cases contain a retrieval query and relevant chunk labels bound to frozen corpus `nsclc-v1`; the five invalid-FHIR cases are retrieval-ineligible.

Regenerate the suite and validate its manifests:

```bash
make generate-week8
make validate-contracts
```

The extraction scorer accepts one JSON prediction per case. A prediction can be either the `/v1/fhir/normalize` response or the canonical case itself:

```bash
python -m evals.scorers.extraction evals/predictions \
  --output evals/reports/extraction.json
```

It reports structural-validation accuracy, micro-averaged required-field precision/recall/F1, exact field provenance, missing-information exact match, and contradiction exact match. Missing predictions fail instead of being silently excluded.

Run the deterministic hybrid-retrieval reference scorer and enforce the Week 8 gate:

```bash
python -m evals.scorers.retrieval \
  --output evals/reports/retrieval-week8.json \
  --fail-below 0.90
```

The report records the suite and corpus versions, corpus hash, embedding provider, retrieval settings, per-case top-five results, recall@1/3/5, hit rate, mean reciprocal rank, and nDCG@5. CI also executes the same cases against PostgreSQL full-text search and pgvector after idempotent corpus ingestion.
