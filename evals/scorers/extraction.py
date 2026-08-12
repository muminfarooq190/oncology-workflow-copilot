"""Score deterministic FHIR validation, extraction, provenance, and escalation outputs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def nested_value(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def normalized(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    if isinstance(value, list):
        items = [normalized(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in sorted(value.items())}
    return value


def exact_match(expected: Any, actual: Any) -> bool:
    return normalized(expected) == normalized(actual)


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def canonical_output(prediction: dict[str, Any]) -> dict[str, Any] | None:
    if "canonicalCase" in prediction:
        return prediction["canonicalCase"]
    if "canonical_case" in prediction:
        return prediction["canonical_case"]
    if "schemaVersion" in prediction and "disease" in prediction:
        return prediction
    return None


def validation_output(prediction: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(prediction.get("validation"), dict):
        return prediction["validation"]
    if "isValid" in prediction or "is_valid" in prediction:
        return prediction
    if "schemaVersion" in prediction and "disease" in prediction:
        return {"isValid": True, "issues": []}
    return None


def actual_biomarker(canonical: dict[str, Any], name: str) -> dict[str, Any] | None:
    biomarkers = nested_value(canonical, "disease.biomarkers") or []
    return next(
        (
            item
            for item in biomarkers
            if isinstance(item, dict) and exact_match(item.get("name"), name)
        ),
        None,
    )


def actual_provenance(canonical: dict[str, Any], field: str) -> list[dict[str, Any]]:
    if field == "patient.sex":
        return nested_value(canonical, "patient.provenance.sex") or []
    if field == "patient.ageYears":
        return nested_value(canonical, "patient.provenance.ageYears") or []
    if field.startswith("disease.primarySite."):
        return nested_value(canonical, "disease.primarySite.provenance") or []
    if field.startswith("disease.histology."):
        return nested_value(canonical, "disease.histology.provenance") or []
    if field.startswith("disease.stage."):
        return nested_value(canonical, "disease.stage.provenance") or []
    if field.startswith("disease.performanceStatus."):
        return nested_value(canonical, "disease.performanceStatus.provenance") or []
    marker_prefix = "disease.biomarkers."
    if field.startswith(marker_prefix):
        biomarker = actual_biomarker(canonical, field.removeprefix(marker_prefix))
        return biomarker.get("provenance", []) if biomarker else []
    return []


def score_case(gold: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    expected_validation = gold.get("expectedValidation", {"valid": True, "issueCodes": []})
    validation = validation_output(prediction)
    actual_valid = None if validation is None else validation.get("isValid", validation.get("is_valid"))
    expected_valid = expected_validation["valid"]
    actual_issue_codes = {
        item.get("code")
        for item in (validation or {}).get("issues", [])
        if isinstance(item, dict)
    }
    expected_issue_codes = set(expected_validation.get("issueCodes", []))
    validation_correct = actual_valid is expected_valid and expected_issue_codes.issubset(
        actual_issue_codes
    )

    canonical = canonical_output(prediction)
    field_counts = Counter(tp=0, fp=0, fn=0)
    field_results: list[dict[str, Any]] = []
    if expected_valid:
        for field, expected in gold.get("expectedFields", {}).items():
            actual = nested_value(canonical or {}, field)
            matched = canonical is not None and exact_match(expected, actual)
            field_counts["tp" if matched else "fn"] += 1
            if not matched and actual is not None:
                field_counts["fp"] += 1
            field_results.append(
                {"field": field, "expected": expected, "actual": actual, "matched": matched}
            )

        for expected in gold.get("expectedBiomarkers", []):
            actual = actual_biomarker(canonical or {}, expected["name"])
            for attribute in ["result", "unit", "status"]:
                metric_field = f"disease.biomarkers.{expected['name']}.{attribute}"
                actual_value = None if actual is None else actual.get(attribute)
                matched = actual is not None and exact_match(expected.get(attribute), actual_value)
                field_counts["tp" if matched else "fn"] += 1
                if not matched and actual_value is not None:
                    field_counts["fp"] += 1
                field_results.append(
                    {
                        "field": metric_field,
                        "expected": expected.get(attribute),
                        "actual": actual_value,
                        "matched": matched,
                    }
                )

    expected_provenance = gold.get("expectedProvenance", {})
    provenance_results = []
    for field, expected in expected_provenance.items():
        actual = actual_provenance(canonical or {}, field)
        matched = exact_match(expected, actual)
        provenance_results.append({"field": field, "matched": matched})

    expected_missing = set(gold.get("expectedMissingInformation", []))
    actual_missing = {
        item.get("field")
        for item in (canonical or {}).get("missingInformation", [])
        if isinstance(item, dict)
    }
    expected_contradictions = set(gold.get("expectedContradictions", []))
    actual_contradictions = {
        item.get("field")
        for item in (canonical or {}).get("contradictions", [])
        if isinstance(item, dict)
    }

    precision = ratio(field_counts["tp"], field_counts["tp"] + field_counts["fp"])
    recall = ratio(field_counts["tp"], field_counts["tp"] + field_counts["fn"])
    return {
        "caseId": gold["caseId"],
        "expectedValid": expected_valid,
        "validationCorrect": validation_correct,
        "fieldCounts": dict(field_counts),
        "fieldPrecision": precision,
        "fieldRecall": recall,
        "fieldF1": f1(precision, recall),
        "fieldResults": field_results,
        "provenanceCorrect": sum(item["matched"] for item in provenance_results),
        "provenanceTotal": len(provenance_results),
        "provenanceResults": provenance_results,
        "missingInformationExact": expected_missing == actual_missing,
        "contradictionsExact": expected_contradictions == actual_contradictions,
    }


def load_predictions(predictions_dir: Path) -> dict[str, dict[str, Any]]:
    predictions: dict[str, dict[str, Any]] = {}
    for path in sorted(predictions_dir.glob("*.json")):
        prediction = json.loads(path.read_text(encoding="utf-8"))
        case_id = prediction.get("caseId") or prediction.get("canonicalCase", {}).get("caseId")
        if case_id is None:
            case_id = path.stem
        predictions[case_id] = prediction
    return predictions


def score_suite(
    predictions: dict[str, dict[str, Any]],
    case_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    selected = set(case_ids) if case_ids is not None else None
    results = []
    for path in sorted((ROOT / "evals" / "cases").glob("*/gold.json")):
        gold = json.loads(path.read_text(encoding="utf-8"))
        case_id = gold["caseId"]
        if selected is not None and case_id not in selected:
            continue
        results.append(score_case(gold, predictions.get(case_id, {})))

    counts = Counter(tp=0, fp=0, fn=0)
    for result in results:
        counts.update(result["fieldCounts"])
    precision = ratio(counts["tp"], counts["tp"] + counts["fp"])
    recall = ratio(counts["tp"], counts["tp"] + counts["fn"])
    provenance_correct = sum(result["provenanceCorrect"] for result in results)
    provenance_total = sum(result["provenanceTotal"] for result in results)
    return {
        "caseCount": len(results),
        "validationAccuracy": ratio(
            sum(result["validationCorrect"] for result in results), len(results)
        ),
        "requiredFieldExtraction": {
            "precision": precision,
            "recall": recall,
            "f1": f1(precision, recall),
            "counts": dict(counts),
        },
        "provenanceExactMatch": ratio(provenance_correct, provenance_total),
        "missingInformationExactMatch": ratio(
            sum(result["missingInformationExact"] for result in results), len(results)
        ),
        "contradictionExactMatch": ratio(
            sum(result["contradictionsExact"] for result in results), len(results)
        ),
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions_dir", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = score_suite(load_predictions(arguments.predictions_dir))
    rendered = json.dumps(report, indent=2) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
