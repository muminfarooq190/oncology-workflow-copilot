"""Freeze source records into a content-addressed evidence corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "evidence" / "corpus" / "nsclc-v1" / "source-records.json"
CHUNK_PATH = SOURCE_PATH.with_name("chunks.json")
MANIFEST_PATH = ROOT / "evidence" / "manifest.json"


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def freeze(source_path: Path = SOURCE_PATH) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    chunks: list[dict[str, Any]] = []
    manifest_sources: list[dict[str, Any]] = []

    for item in source["sources"]:
        chunk_ids = []
        for raw_chunk in item["chunks"]:
            chunk_ids.append(raw_chunk["chunkId"])
            content_hash = sha256(raw_chunk["content"].encode())
            chunks.append(
                {
                    **raw_chunk,
                    "sourceId": item["sourceId"],
                    "sourceClass": item["sourceClass"],
                    "sourceTitle": item["sourceTitle"],
                    "sourceUrl": item["sourceUrl"],
                    "publicationDate": item["publicationDate"],
                    "contentHash": content_hash,
                    "ingestedAt": source["frozenAt"],
                    "licenseStatus": item["licenseStatus"],
                    "tumorType": "NSCLC",
                    "corpusVersion": source["corpusVersion"],
                }
            )
        manifest_sources.append(
            {
                key: item[key]
                for key in (
                    "sourceId",
                    "sourceClass",
                    "sourceTitle",
                    "sourceUrl",
                    "publicationDate",
                    "licenseStatus",
                )
            }
            | {"chunkIds": chunk_ids}
        )

    chunks.sort(key=lambda item: item["chunkId"])
    corpus_hash = sha256(
        canonical_json(
            [{"chunkId": item["chunkId"], "contentHash": item["contentHash"]} for item in chunks]
        )
    )
    manifest = {
        "corpusVersion": source["corpusVersion"],
        "status": "frozen",
        "frozenAt": source["frozenAt"],
        "clinicalScope": source["clinicalScope"],
        "embedding": source["embedding"],
        "retrieval": source["retrieval"],
        "chunkFile": "corpus/nsclc-v1/chunks.json",
        "chunkCount": len(chunks),
        "corpusHash": corpus_hash,
        "allowedSourceClasses": sorted({item["sourceClass"] for item in source["sources"]}),
        "requiredChunkMetadata": [
            "chunkId",
            "sourceTitle",
            "sourceUrl",
            "publicationDate",
            "locator",
            "contentHash",
            "ingestedAt",
            "licenseStatus",
            "tumorType",
            "corpusVersion",
        ],
        "sources": manifest_sources,
    }
    return manifest, chunks


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    manifest, chunks = freeze()
    write_json(CHUNK_PATH, chunks)
    write_json(MANIFEST_PATH, manifest)
    print(
        f"Frozen {manifest['chunkCount']} evidence chunks as {manifest['corpusVersion']} "
        f"({manifest['corpusHash']})."
    )


if __name__ == "__main__":
    main()
