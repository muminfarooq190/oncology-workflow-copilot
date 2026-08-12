# Evaluation suite

Each case directory contains a case manifest, a synthetic FHIR input reference, and clinician-adjudicated gold labels. Development cases may evolve. Validation labels are changed only through an adjudication change record. Locked-test labels remain unavailable to prompt and retrieval tuning until launch review.

`nsclc-001` is the first development case. Its extraction labels are seeded, but its evidence labels intentionally remain empty until the `nsclc-v1` corpus is frozen.

