#!/usr/bin/env python3
"""Validate repository-owned JSON contracts and synthetic evaluation manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:  # Local minimal environments; CI installs jsonschema for full validation.
    Draft202012Validator = None  # type: ignore[assignment,misc]

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_PARTITIONS = {"development", "validation", "locked_test"}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc


def validate_json_files() -> int:
    paths = sorted(ROOT.glob("**/*.json"))
    for path in paths:
        if "node_modules" not in path.parts:
            load_json(path)
    return sum("node_modules" not in path.parts for path in paths)


def validate_contracts() -> int:
    contracts = sorted((ROOT / "contracts").glob("**/*.schema.json"))
    for path in contracts:
        schema = load_json(path)
        assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
        assert schema.get("type") == "object"
        assert isinstance(schema.get("properties"), dict)
        if Draft202012Validator is not None:
            Draft202012Validator.check_schema(schema)
    return len(contracts)


def is_explicitly_synthetic(bundle: dict[str, Any]) -> bool:
    tags = bundle.get("meta", {}).get("tag", [])
    return any(
        isinstance(tag, dict)
        and tag.get("system") == "https://oncology-copilot.dev/tags"
        and tag.get("code") == "synthetic"
        for tag in tags
    )


def validate_eval_cases() -> int:
    manifests = sorted((ROOT / "evals" / "cases").glob("*/case.json"))
    case_ids: set[str] = set()

    for manifest_path in manifests:
        manifest = load_json(manifest_path)
        case_id = manifest["caseId"]
        assert case_id not in case_ids, f"Duplicate caseId: {case_id}"
        case_ids.add(case_id)
        assert manifest["partition"] in ALLOWED_PARTITIONS, f"Invalid partition for {case_id}"
        assert manifest["clinicalScope"] == "NSCLC", f"Unsupported scope for {case_id}"

        input_path = (manifest_path.parent / manifest["input"]).resolve()
        assert input_path.is_relative_to(ROOT), f"Input escapes repository: {case_id}"
        assert input_path.exists(), f"Missing input for {case_id}: {input_path}"
        bundle = load_json(input_path)
        assert bundle.get("resourceType") == "Bundle", f"Input is not a Bundle: {case_id}"
        assert is_explicitly_synthetic(bundle), f"Missing synthetic marker: {case_id}"

        resources = [entry.get("resource", {}) for entry in bundle.get("entry", [])]
        assert any(item.get("resourceType") == "Patient" for item in resources), (
            f"Bundle has no Patient: {case_id}"
        )

        gold_path = manifest_path.parent / manifest["gold"]
        gold = load_json(gold_path)
        assert gold["caseId"] == case_id, f"Gold caseId mismatch: {case_id}"

    return len(manifests)


def main() -> None:
    json_count = validate_json_files()
    contract_count = validate_contracts()
    case_count = validate_eval_cases()
    print(
        f"Repository validation passed: {json_count} JSON files, "
        f"{contract_count} schemas, {case_count} evaluation case(s)."
    )


if __name__ == "__main__":
    main()
