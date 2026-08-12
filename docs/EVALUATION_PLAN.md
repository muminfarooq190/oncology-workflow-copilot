# Evaluation plan

## Objective

Determine whether the complete workflow can prepare an accurate, traceable NSCLC tumor-board draft, appropriately abstain or escalate, and reduce clinician effort without hiding unsafe errors behind aggregate scores.

## Evaluation-driven development

Evaluation cases are introduced with the feature they test. The final 20-case test partition remains locked until launch review. Model prompts, retrieval settings, and rules may not be tuned against the locked partition.

## Dataset

The target suite contains 100 synthetic cases.

| Category | Cases | Purpose |
|---|---:|---|
| Typical and reasonably complete | 40 | Main workflow distribution |
| Missing required information | 20 | Completeness and escalation |
| Contradictory data | 15 | Cross-document conflict handling |
| Rare or ambiguous | 10 | Uncertainty and scope boundaries |
| Adversarial/prompt injection | 10 | Instruction and data-boundary safety |
| Invalid FHIR | 5 | Validation and failure behavior |

Partition: 60 development, 20 validation, and 20 locked test cases. Stratification preserves category coverage.

## Gold labels

Every case contains:

- Expected canonical fields and field-level provenance.
- Expected missing fields and contradictions.
- Relevant evidence chunk IDs.
- Supported claims and prohibited claims.
- Required escalation labels.
- A clinician-authored or clinician-adjudicated reference packet.

Models may help draft synthetic cases but cannot establish their own ground truth. A clinician must adjudicate clinical labels before a case enters validation or test partitions.

## Metrics

| Metric | Definition | Launch target |
|---|---|---:|
| Required-field extraction | Micro-averaged precision, recall, and F1 across required canonical fields | F1 >= 0.95 |
| Critical-field accuracy | Exact normalized match for histology, stage, actionable biomarkers, and treatment | >= 0.98 |
| Retrieval recall@5 | Gold relevant chunks found in the top five unique results | >= 0.90 |
| Citation support | Material claims fully entailed by cited evidence | >= 0.95 |
| Unsupported-claim rate | Material claims not supported by record or cited evidence | <= 0.02 |
| Clinician correction rate | Severity-weighted changed claims divided by reviewed claims | <= 0.15 |
| Escalation sensitivity | Required-escalation cases correctly escalated | 1.00 |
| Escalation precision | Correct escalations divided by all escalations | Report; initial target >= 0.80 |
| Latency | End-to-end workflow p95 excluding clinician time | < 45 seconds |
| Cost | Model and embedding cost per completed case | <= USD 0.25 initial target |

## Correction severity

- `0`: formatting only.
- `1`: non-clinical wording or ordering.
- `2`: relevant omission or imprecision without likely treatment consequence.
- `5`: stage, histology, biomarker, treatment, contraindication, or other change with plausible clinical consequence.

Both raw and weighted correction rates are reported. Averages may not hide any severity-5 correction.

## Scoring hierarchy

1. Deterministic comparison for structured fields, schemas, latency, tokens, and cost.
2. Rule-based citation and provenance checks.
3. Reference-guided model grading for semantic support, using a binary rubric.
4. Clinician adjudication for sampled disagreements and all critical claims.

Model graders are calibrated against clinician labels, and agreement is reported. Model-judge scores are not treated as ground truth.

## Continuous evaluation

- Pull requests run a fast representative subset with deterministic stubs.
- Scheduled or manually triggered jobs run the full development/validation suites with configured models.
- A prompt, model, corpus, schema, or retrieval-setting change produces a versioned comparison report.
- Production-like review corrections become candidates for new synthetic regression cases after de-identification is proven; real data is outside this repository's scope.

## Failure taxonomy

Every failed case receives one primary cause: ingestion, normalization, missingness rule, contradiction rule, retrieval, generation, citation, escalation, authorization, infrastructure, or gold-label defect.

