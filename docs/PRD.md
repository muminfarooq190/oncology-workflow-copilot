# Product requirements document

## Product statement

Oncology Workflow Copilot reduces the clerical and synthesis work required to prepare an NSCLC tumor-board case while preserving clinician control. It converts a synthetic FHIR R4 record into a structured, cited draft, highlights missing or contradictory information, and records every input, transformation, evidence item, model version, output, correction, and approval.

## Problem

Tumor-board preparation requires clinicians to reconstruct disease history across fragmented pathology, imaging, molecular, laboratory, and treatment records. Missing biomarkers, incompatible staging assertions, and incomplete treatment timelines are easy to overlook. Generic chat interfaces hide provenance and cannot provide an auditable, measurable workflow.

## Primary users

- **Tumor-board coordinator:** imports a case, resolves basic validation problems, and tracks readiness.
- **Medical oncologist:** reviews clinical synthesis, citations, missing information, contradictions, and discussion points.
- **Clinical reviewer/evaluator:** adjudicates gold labels and evaluates system failures.
- **Administrator/auditor:** manages access and inspects immutable workflow events.

## Initial scope

- Adult synthetic NSCLC cases.
- FHIR R4 JSON Bundles.
- Structured extraction of demographics, disease, stage, pathology, biomarkers, imaging, treatment, performance status, and relevant organ function.
- Completeness and contradiction rules.
- Retrieval from a frozen, versioned public evidence corpus.
- A clinician-reviewable preparation packet with claim-level citations.
- Correction, approval, escalation, and audit capture.

## Explicit non-goals

- Diagnosis, autonomous treatment selection, prescribing, or ordering.
- Patient-facing advice.
- Processing real PHI in this portfolio environment.
- Comprehensive coverage of every malignancy.
- Integration with a proprietary EHR or paid guideline corpus.
- Claims of HIPAA, GDPR, MDR, or other regulatory compliance.

## Golden-path user journey

1. The coordinator selects or uploads a synthetic FHIR bundle.
2. The system validates format, references, required fields, and supported scope.
3. The system displays a normalized oncology timeline with source provenance.
4. Deterministic rules identify missing and contradictory information.
5. The workflow retrieves versioned evidence and creates a draft packet.
6. The oncologist inspects citations, edits claims, selects correction reasons, and approves or escalates.
7. The system stores the final packet and append-only audit events.

## Functional requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| FR-01 | Accept a FHIR R4 Bundle and reject unsupported or malformed input | Contract and integration tests |
| FR-02 | Normalize supported resources into canonical schema v1 | Field-level gold labels |
| FR-03 | Preserve source resource and JSON-path provenance | Provenance assertions |
| FR-04 | Detect defined missing fields and contradictions | Rule test suite |
| FR-05 | Retrieve only from a frozen evidence corpus version | Retrieval manifest and hash |
| FR-06 | Attach evidence to each material clinical claim | Citation-support scorer |
| FR-07 | Prevent finalization until an authorized clinician approves | RBAC integration test |
| FR-08 | Escalate configured high-risk conditions | 100% mandatory-escalation sensitivity |
| FR-09 | Store model, prompt, corpus, contract, input, output, and correction versions | Audit assertions |
| FR-10 | Expose latency, token/cost, error, retrieval, and correction metrics | Telemetry dashboard |

## Success measures

- Reduced median clinician preparation/review time against a manual baseline.
- Required-field extraction micro-F1 at or above the launch threshold.
- Retrieval and citation support at or above the launch threshold.
- No critical unsafe errors on the locked test set.
- Mandatory escalation sensitivity of 100% on the locked test set.

## Product risks

- Synthetic data may fail to represent real record fragmentation.
- A model-generated “gold” dataset can create circular validation.
- Citation presence can be mistaken for citation support.
- Aggregate accuracy can hide dangerous errors in stage, pathology, or biomarkers.
- Infrastructure breadth can displace work on clinical correctness.

These risks are controlled through clinician-adjudicated labels, critical-field metrics, a frozen test set, claim-level verification, and staged infrastructure work.

