"""Validate repository-owned JSON contracts and synthetic evaluation manifests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:  # Local minimal environments; CI installs jsonschema for full validation.
    Draft202012Validator = None  # type: ignore[assignment,misc]

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_PARTITIONS = {"development", "validation", "locked_test"}
EXCLUDED_DIRECTORIES = {".git", ".venv", "dist", "node_modules"}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def validate_json_files() -> int:
    paths = [
        path
        for path in sorted(ROOT.glob("**/*.json"))
        if not EXCLUDED_DIRECTORIES.intersection(path.relative_to(ROOT).parts)
    ]
    for path in paths:
        load_json(path)
    return len(paths)


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


def validate_evidence() -> tuple[str, set[str]]:
    manifest_path = ROOT / "evidence" / "manifest.json"
    manifest = load_json(manifest_path)
    chunk_path = (manifest_path.parent / manifest["chunkFile"]).resolve()
    assert chunk_path.is_relative_to(ROOT), "Evidence chunk file escapes repository"
    chunks = load_json(chunk_path)
    assert manifest["status"] == "frozen", "Evidence corpus must be frozen"
    assert manifest["chunkCount"] == len(chunks), "Evidence chunk count mismatch"
    required = set(manifest["requiredChunkMetadata"])
    chunk_ids: set[str] = set()
    digest_input = []
    for chunk in chunks:
        assert required <= chunk.keys(), f"Missing evidence metadata: {chunk.get('chunkId')}"
        chunk_id = chunk["chunkId"]
        assert chunk_id not in chunk_ids, f"Duplicate evidence chunk: {chunk_id}"
        chunk_ids.add(chunk_id)
        assert chunk["corpusVersion"] == manifest["corpusVersion"]
        assert sha256(chunk["content"].encode()) == chunk["contentHash"], (
            f"Evidence content hash mismatch: {chunk_id}"
        )
        digest_input.append({"chunkId": chunk_id, "contentHash": chunk["contentHash"]})
    assert sha256(canonical_json(sorted(digest_input, key=lambda item: item["chunkId"]))) == (
        manifest["corpusHash"]
    ), "Evidence corpus hash mismatch"
    return manifest["corpusVersion"], chunk_ids


def validate_eval_cases(evidence_version: str, evidence_chunk_ids: set[str]) -> set[str]:
    manifests = sorted((ROOT / "evals" / "cases").glob("*/case.json"))
    case_ids: set[str] = set()

    for manifest_path in manifests:
        manifest = load_json(manifest_path)
        gold_path = manifest_path.parent / manifest["gold"]
        gold = load_json(gold_path)
        case_id = manifest["caseId"]
        assert case_id not in case_ids, f"Duplicate caseId: {case_id}"
        case_ids.add(case_id)
        assert manifest["partition"] in ALLOWED_PARTITIONS, f"Invalid partition for {case_id}"
        assert manifest["clinicalScope"] == "NSCLC", f"Unsupported scope for {case_id}"
        assert manifest["syntheticFixture"] is True, f"Fixture is not declared synthetic: {case_id}"
        assert manifest["clinicianAdjudication"]["status"] in {"pending", "adjudicated"}

        input_path = (manifest_path.parent / manifest["input"]).resolve()
        assert input_path.is_relative_to(ROOT), f"Input escapes repository: {case_id}"
        assert input_path.exists(), f"Missing input for {case_id}: {input_path}"
        bundle = load_json(input_path)
        expected_valid = gold["expectedValidation"]["valid"]
        if expected_valid:
            assert bundle.get("resourceType") == "Bundle", f"Input is not a Bundle: {case_id}"
            assert is_explicitly_synthetic(bundle), f"Missing synthetic marker: {case_id}"

        resources = [entry.get("resource", {}) for entry in bundle.get("entry", [])]
        if expected_valid:
            assert any(item.get("resourceType") == "Patient" for item in resources), (
                f"Bundle has no Patient: {case_id}"
            )
        assert gold["caseId"] == case_id, f"Gold caseId mismatch: {case_id}"
        assert isinstance(gold["expectedFields"], dict), f"Missing field gold: {case_id}"
        assert isinstance(gold["expectedBiomarkers"], list), f"Missing biomarker gold: {case_id}"
        assert isinstance(gold["expectedProvenance"], dict), f"Missing provenance gold: {case_id}"
        assert gold["evidenceCorpusVersion"] == evidence_version, (
            f"Evidence version mismatch: {case_id}"
        )
        relevant = set(gold["goldRelevantEvidenceChunkIds"])
        assert relevant <= evidence_chunk_ids, f"Unknown evidence chunk in gold: {case_id}"
        if expected_valid:
            assert gold["retrievalQuery"].strip(), f"Missing retrieval query: {case_id}"
            assert relevant, f"Missing retrieval relevance gold: {case_id}"
        else:
            assert not gold["retrievalQuery"], f"Invalid case has retrieval query: {case_id}"
            assert not relevant, f"Invalid case has retrieval relevance gold: {case_id}"

    return case_ids


def main() -> None:
    json_count = validate_json_files()
    contract_count = validate_contracts()
    evidence_version, evidence_chunk_ids = validate_evidence()
    case_ids = validate_eval_cases(evidence_version, evidence_chunk_ids)
    case_count = len(case_ids)
    suite = load_json(ROOT / "evals" / "suite-manifest.json")
    assert suite["caseCount"] == case_count, "Suite manifest case count does not match case files"
    suite_case_ids = {item["caseId"] for item in suite["cases"]}
    assert suite_case_ids == case_ids, "Suite manifest case IDs do not match case files"
    print(
        f"Repository validation passed: {json_count} JSON files, "
        f"{contract_count} schemas, {case_count} evaluation case(s), "
        f"{len(evidence_chunk_ids)} frozen evidence chunk(s)."
    )


if __name__ == "__main__":
    main()
