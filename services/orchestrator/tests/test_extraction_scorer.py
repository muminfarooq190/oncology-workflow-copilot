import pytest
from evals.scorers.extraction import score_case, score_suite


def gold() -> dict:
    return {
        "caseId": "unit-case",
        "expectedValidation": {"valid": True, "issueCodes": []},
        "expectedFields": {
            "patient.sex": "female",
            "disease.stage.group": "IVA",
        },
        "expectedBiomarkers": [
            {"name": "EGFR", "result": "L858R", "unit": None, "status": "positive"}
        ],
        "expectedProvenance": {
            "disease.stage.group": [
                {
                    "resourceType": "Observation",
                    "resourceId": "stage-1",
                    "jsonPath": "$.entry[2].resource.valueCodeableConcept",
                }
            ]
        },
        "expectedMissingInformation": [],
        "expectedContradictions": [],
    }


def complete_prediction() -> dict:
    return {
        "validation": {"isValid": True, "issues": []},
        "canonicalCase": {
            "schemaVersion": "1.0.0",
            "caseId": "unit-case",
            "patient": {"sex": "female"},
            "disease": {
                "stage": {
                    "group": "IVA",
                    "provenance": [
                        {
                            "resourceType": "Observation",
                            "resourceId": "stage-1",
                            "jsonPath": "$.entry[2].resource.valueCodeableConcept",
                        }
                    ],
                },
                "biomarkers": [
                    {
                        "name": "EGFR",
                        "result": "L858R",
                        "unit": None,
                        "status": "positive",
                        "provenance": [],
                    }
                ],
            },
            "missingInformation": [],
            "contradictions": [],
        },
    }


def test_score_case_accepts_exact_fields_biomarkers_and_provenance() -> None:
    report = score_case(gold(), complete_prediction())

    assert report["validationCorrect"] is True
    assert report["fieldF1"] == 1.0
    assert report["provenanceCorrect"] == report["provenanceTotal"] == 1
    assert report["missingInformationExact"] is True


def test_wrong_value_counts_as_false_positive_and_false_negative() -> None:
    prediction = complete_prediction()
    prediction["canonicalCase"]["disease"]["stage"]["group"] = "IIIB"

    report = score_case(gold(), prediction)

    assert report["fieldCounts"] == {"tp": 4, "fp": 1, "fn": 1}
    assert report["fieldF1"] == pytest.approx(0.8)


def test_suite_scores_missing_predictions_as_failures() -> None:
    report = score_suite({}, case_ids=["nsclc-001"])

    assert report["caseCount"] == 1
    assert report["validationAccuracy"] == 0.0
    assert report["requiredFieldExtraction"]["recall"] == 0.0
