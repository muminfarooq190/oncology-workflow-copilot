import json
import os
from pathlib import Path

import httpx
import pytest

from app.db import get_session_factory
from app.evidence import HybridRetriever, ingest_corpus
from app.main import app

ROOT = Path(__file__).resolve().parents[3]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="requires PostgreSQL with pgvector",
    ),
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_ingestion_is_idempotent_and_database_retrieval_meets_gate() -> None:
    manifest_path = ROOT / "evidence" / "manifest.json"
    first = await ingest_corpus(get_session_factory(), manifest_path)
    replay = await ingest_corpus(get_session_factory(), manifest_path)

    assert first.chunk_count == 19
    assert replay.created is False
    assert replay.corpus_hash == first.corpus_hash

    retriever = HybridRetriever(get_session_factory())
    suite = load_json(ROOT / "evals" / "suite-manifest.json")
    relevant_total = 0
    retrieved_total = 0
    for case in suite["cases"]:
        gold = load_json(ROOT / "evals" / "cases" / case["caseId"] / "gold.json")
        relevant = set(gold["goldRelevantEvidenceChunkIds"])
        if not relevant:
            continue
        results = await retriever.search(
            gold["retrievalQuery"], corpus_version=gold["evidenceCorpusVersion"], top_k=5
        )
        relevant_total += len(relevant)
        retrieved_total += len(relevant.intersection(result.chunk_id for result in results))

    assert retrieved_total / relevant_total >= 0.90


@pytest.mark.asyncio
async def test_evidence_search_endpoint_returns_reviewable_source_metadata() -> None:
    await ingest_corpus(get_session_factory(), ROOT / "evidence" / "manifest.json")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/evidence/search",
            json={"query": "MET exon 14 skipping metastatic NSCLC tepotinib", "topK": 5},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["corpusVersion"] == "nsclc-v1"
    assert body["embeddingProvider"] == "clinical-hash-embedding-v1"
    assert body["results"][0]["chunkId"] == "fda-tepotinib-met-001"
    assert body["results"][0]["sourceUrl"].startswith("https://www.fda.gov/")
    assert body["results"][0]["contentHash"].startswith("sha256:")
    assert body["results"][0]["lexicalRank"] is not None
    assert body["results"][0]["vectorRank"] is not None
