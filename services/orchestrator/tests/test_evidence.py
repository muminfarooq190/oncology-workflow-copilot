from pathlib import Path

from evals.scorers.retrieval import score_suite

from app.embedding import DIMENSIONS, cosine_similarity, embed
from app.evidence import load_corpus

ROOT = Path(__file__).resolve().parents[3]


def test_hash_embedding_is_deterministic_and_normalized() -> None:
    first = embed("EGFR-mutated non-small cell lung cancer")
    second = embed("EGFR-mutated NSCLC")

    assert len(first) == DIMENSIONS
    assert first == embed("EGFR-mutated non-small cell lung cancer")
    assert cosine_similarity(first, second) > 0.5


def test_frozen_corpus_hashes_and_embedding_contract_validate() -> None:
    manifest, chunks = load_corpus(ROOT / "evidence" / "manifest.json")

    assert manifest["status"] == "frozen"
    assert manifest["chunkCount"] == len(chunks) == 19


def test_retrieval_development_gate_passes() -> None:
    report = score_suite()

    assert report["suiteCaseCount"] == 60
    assert report["eligibleCaseCount"] == 55
    assert report["metrics"]["recallAt5"] >= 0.90
    assert report["exitCriterion"]["passed"] is True
