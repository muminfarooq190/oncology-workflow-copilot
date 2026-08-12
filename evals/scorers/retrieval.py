"""Run the deterministic Week 8 hybrid-retrieval evaluation."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.orchestrator.app.embedding import (
    PROVIDER,
    cosine_similarity,
    embed,
    lexical_tokens,
)
from services.orchestrator.app.evidence import embedding_text

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "evidence" / "manifest.json"
DEFAULT_REPORT = ROOT / "evals" / "reports" / "retrieval-week8.json"


@dataclass(frozen=True)
class RankedChunk:
    chunk_id: str
    lexical_rank: int | None
    vector_rank: int | None
    rrf_score: float


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rank_chunks(
    query: str,
    chunks: list[dict[str, Any]],
    *,
    candidate_limit: int = 50,
    rrf_k: int = 60,
) -> list[RankedChunk]:
    query_tokens = set(lexical_tokens(query))
    lexical_scores = []
    vector_scores = []
    query_vector = embed(query)
    for chunk in chunks:
        searchable = embedding_text(chunk)
        chunk_tokens = lexical_tokens(searchable)
        overlap = sum(1 for token in chunk_tokens if token in query_tokens)
        if overlap:
            lexical_scores.append((overlap / math.sqrt(len(chunk_tokens)), chunk["chunkId"]))
        vector_scores.append((cosine_similarity(query_vector, embed(searchable)), chunk["chunkId"]))

    lexical_scores.sort(key=lambda item: (-item[0], item[1]))
    vector_scores.sort(key=lambda item: (-item[0], item[1]))
    lexical_ranks = {
        chunk_id: rank
        for rank, (_, chunk_id) in enumerate(lexical_scores[:candidate_limit], start=1)
    }
    vector_ranks = {
        chunk_id: rank
        for rank, (_, chunk_id) in enumerate(vector_scores[:candidate_limit], start=1)
    }
    ranked = []
    for chunk_id in lexical_ranks.keys() | vector_ranks.keys():
        lexical_rank = lexical_ranks.get(chunk_id)
        vector_rank = vector_ranks.get(chunk_id)
        score = sum(
            1 / (rrf_k + rank)
            for rank in (lexical_rank, vector_rank)
            if rank is not None
        )
        ranked.append(RankedChunk(chunk_id, lexical_rank, vector_rank, score))
    return sorted(ranked, key=lambda item: (-item.rrf_score, item.chunk_id))


def _reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    return next((1 / rank for rank, item in enumerate(retrieved, 1) if item in relevant), 0.0)


def _ndcg(retrieved: list[str], relevant: set[str], k: int) -> float:
    dcg = sum(
        1 / math.log2(rank + 1)
        for rank, item in enumerate(retrieved[:k], 1)
        if item in relevant
    )
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(k, len(relevant)) + 1))
    return dcg / ideal if ideal else 1.0


def score_suite(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    chunks = load_json(manifest_path.parent / manifest["chunkFile"])
    suite = load_json(ROOT / "evals" / "suite-manifest.json")
    chunk_ids = {chunk["chunkId"] for chunk in chunks}
    cases = []
    relevant_total = 0
    hits = {1: 0, 3: 0, 5: 0}
    reciprocal_ranks = []
    ndcg_values = []
    skipped = 0

    for case in suite["cases"]:
        gold = load_json(ROOT / "evals" / "cases" / case["caseId"] / "gold.json")
        relevant = set(gold["goldRelevantEvidenceChunkIds"])
        if not relevant:
            skipped += 1
            continue
        if not relevant <= chunk_ids:
            raise ValueError(f"{case['caseId']} references unknown evidence chunks")
        ranked = rank_chunks(
            gold["retrievalQuery"],
            chunks,
            candidate_limit=manifest["retrieval"]["candidateLimit"],
            rrf_k=manifest["retrieval"]["rrfK"],
        )
        retrieved = [item.chunk_id for item in ranked]
        relevant_total += len(relevant)
        case_hits = {}
        for k in hits:
            count = len(relevant.intersection(retrieved[:k]))
            hits[k] += count
            case_hits[f"recallAt{k}"] = count / len(relevant)
        reciprocal_rank = _reciprocal_rank(retrieved, relevant)
        ndcg = _ndcg(retrieved, relevant, 5)
        reciprocal_ranks.append(reciprocal_rank)
        ndcg_values.append(ndcg)
        cases.append(
            {
                "caseId": case["caseId"],
                "query": gold["retrievalQuery"],
                "relevantChunkIds": sorted(relevant),
                "retrievedChunkIds": retrieved[:5],
                **case_hits,
                "reciprocalRank": reciprocal_rank,
                "ndcgAt5": ndcg,
            }
        )

    metrics = {f"recallAt{k}": hits[k] / relevant_total for k in hits}
    metrics.update(
        {
            "hitRateAt5": sum(item["recallAt5"] > 0 for item in cases) / len(cases),
            "meanReciprocalRank": sum(reciprocal_ranks) / len(reciprocal_ranks),
            "ndcgAt5": sum(ndcg_values) / len(ndcg_values),
        }
    )
    threshold = 0.90
    return {
        "reportVersion": "week8-retrieval-v1",
        "generatedBy": "evals.scorers.retrieval",
        "suiteVersion": suite["suiteVersion"],
        "suiteCaseCount": suite["caseCount"],
        "eligibleCaseCount": len(cases),
        "skippedCaseCount": skipped,
        "corpusVersion": manifest["corpusVersion"],
        "corpusHash": manifest["corpusHash"],
        "embeddingProvider": PROVIDER,
        "retrieval": manifest["retrieval"],
        "metrics": metrics,
        "exitCriterion": {
            "metric": "recallAt5",
            "threshold": threshold,
            "passed": metrics["recallAt5"] >= threshold,
        },
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--fail-below", type=float, default=0.90)
    args = parser.parse_args()
    report = score_suite(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    recall_at_5 = report["metrics"]["recallAt5"]
    print(
        f"Retrieval recall@5={recall_at_5:.3f} across "
        f"{report['eligibleCaseCount']} eligible cases."
    )
    if recall_at_5 < args.fail_below:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
