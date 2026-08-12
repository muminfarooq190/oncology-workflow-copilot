"""Frozen evidence ingestion and PostgreSQL hybrid retrieval."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db_models import EvidenceChunkRecord, EvidenceCorpusRecord
from app.embedding import DIMENSIONS, PROVIDER, embed


class CorpusError(RuntimeError):
    """Base error for an invalid or unavailable evidence corpus."""


class CorpusConflict(CorpusError):
    """The immutable corpus version already exists with different content."""


class CorpusNotFound(CorpusError):
    """The requested corpus has not been ingested."""


@dataclass(frozen=True)
class IngestionResult:
    corpus_version: str
    chunk_count: int
    created: bool
    corpus_hash: str
    manifest_hash: str


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    source_title: str
    source_url: str
    publication_date: date
    locator: str
    content: str
    content_hash: str
    tags: list[str]
    lexical_rank: int | None
    vector_rank: int | None
    rrf_score: float


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_corpus(manifest_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chunk_path = manifest_path.parent / manifest["chunkFile"]
    chunks = json.loads(chunk_path.read_text(encoding="utf-8"))
    if not isinstance(chunks, list):
        raise CorpusError("chunk file must contain a JSON array")
    if manifest["status"] != "frozen":
        raise CorpusError("only frozen evidence corpora may be ingested")
    if manifest["embedding"] != {"provider": PROVIDER, "dimensions": DIMENSIONS}:
        raise CorpusError("corpus embedding contract does not match this service")
    if manifest["chunkCount"] != len(chunks):
        raise CorpusError("manifest chunkCount does not match chunk file")

    required = set(manifest["requiredChunkMetadata"])
    seen: set[str] = set()
    for chunk in chunks:
        missing = required - chunk.keys()
        if missing:
            raise CorpusError(f"{chunk.get('chunkId', '<unknown>')} missing {sorted(missing)}")
        chunk_id = chunk["chunkId"]
        if chunk_id in seen:
            raise CorpusError(f"duplicate chunkId: {chunk_id}")
        seen.add(chunk_id)
        if chunk["corpusVersion"] != manifest["corpusVersion"]:
            raise CorpusError(f"{chunk_id} has the wrong corpusVersion")
        if sha256(chunk["content"].encode()) != chunk["contentHash"]:
            raise CorpusError(f"{chunk_id} contentHash mismatch")

    digest_input = [
        {"chunkId": chunk["chunkId"], "contentHash": chunk["contentHash"]}
        for chunk in sorted(chunks, key=lambda item: item["chunkId"])
    ]
    if sha256(canonical_json(digest_input)) != manifest["corpusHash"]:
        raise CorpusError("corpusHash mismatch")
    return manifest, chunks


async def ingest_corpus(
    session_factory: async_sessionmaker[AsyncSession], manifest_path: Path
) -> IngestionResult:
    manifest, chunks = load_corpus(manifest_path)
    manifest_hash = sha256(canonical_json(manifest))
    version = manifest["corpusVersion"]

    async with session_factory() as session, session.begin():
        existing = await session.get(EvidenceCorpusRecord, version)
        if existing:
            if (
                existing.manifest_hash != manifest_hash
                or existing.corpus_hash != manifest["corpusHash"]
            ):
                raise CorpusConflict(
                    f"corpus version {version} already exists with different immutable content"
                )
            return IngestionResult(
                corpus_version=version,
                chunk_count=len(chunks),
                created=False,
                corpus_hash=existing.corpus_hash,
                manifest_hash=existing.manifest_hash,
            )

        session.add(
            EvidenceCorpusRecord(
                version=version,
                manifest_hash=manifest_hash,
                corpus_hash=manifest["corpusHash"],
                status=manifest["status"],
                embedding_provider=manifest["embedding"]["provider"],
                embedding_dimensions=manifest["embedding"]["dimensions"],
                frozen_at=_parse_datetime(manifest["frozenAt"]),
            )
        )
        session.add_all(
            EvidenceChunkRecord(
                chunk_id=chunk["chunkId"],
                corpus_version=chunk["corpusVersion"],
                source_id=chunk["sourceId"],
                source_title=chunk["sourceTitle"],
                source_url=chunk["sourceUrl"],
                publication_date=date.fromisoformat(chunk["publicationDate"]),
                locator=chunk["locator"],
                content=chunk["content"],
                content_hash=chunk["contentHash"],
                license_status=chunk["licenseStatus"],
                tumor_type=chunk["tumorType"],
                tags=chunk.get("tags", []),
                embedding=embed(embedding_text(chunk)),
            )
            for chunk in chunks
        )

    return IngestionResult(
        corpus_version=version,
        chunk_count=len(chunks),
        created=True,
        corpus_hash=manifest["corpusHash"],
        manifest_hash=manifest_hash,
    )


def embedding_text(chunk: dict[str, Any]) -> str:
    return " ".join(
        [chunk["sourceTitle"], chunk["locator"], *chunk.get("tags", []), chunk["content"]]
    )


class HybridRetriever:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        candidate_limit: int = 50,
        rrf_k: int = 60,
    ) -> None:
        self._session_factory = session_factory
        self._candidate_limit = candidate_limit
        self._rrf_k = rrf_k

    async def search(
        self,
        query: str,
        *,
        corpus_version: str,
        tumor_type: str = "NSCLC",
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        query_vector = embed(query)
        async with self._session_factory() as session:
            corpus = await session.get(EvidenceCorpusRecord, corpus_version)
            if not corpus:
                raise CorpusNotFound(f"evidence corpus {corpus_version} is not ingested")
            if (
                corpus.embedding_provider != PROVIDER
                or corpus.embedding_dimensions != DIMENSIONS
            ):
                raise CorpusConflict("stored corpus has an incompatible embedding contract")

            tsquery = func.websearch_to_tsquery("english", query)
            lexical_score = func.ts_rank_cd(
                EvidenceChunkRecord.search_vector, tsquery
            ).label("lexical_score")
            lexical_rows = (
                await session.execute(
                    select(EvidenceChunkRecord, lexical_score)
                    .where(
                        EvidenceChunkRecord.corpus_version == corpus_version,
                        EvidenceChunkRecord.tumor_type == tumor_type,
                        EvidenceChunkRecord.search_vector.op("@@")(tsquery),
                    )
                    .order_by(lexical_score.desc(), EvidenceChunkRecord.chunk_id)
                    .limit(self._candidate_limit)
                )
            ).all()

            distance = EvidenceChunkRecord.embedding.cosine_distance(query_vector).label(
                "distance"
            )
            vector_rows = (
                await session.execute(
                    select(EvidenceChunkRecord, distance)
                    .where(
                        EvidenceChunkRecord.corpus_version == corpus_version,
                        EvidenceChunkRecord.tumor_type == tumor_type,
                    )
                    .order_by(distance, EvidenceChunkRecord.chunk_id)
                    .limit(self._candidate_limit)
                )
            ).all()

        lexical_ranks = {row[0].chunk_id: rank for rank, row in enumerate(lexical_rows, 1)}
        vector_ranks = {row[0].chunk_id: rank for rank, row in enumerate(vector_rows, 1)}
        records = {row[0].chunk_id: row[0] for row in [*lexical_rows, *vector_rows]}
        scored = []
        for chunk_id, record in records.items():
            lexical_rank = lexical_ranks.get(chunk_id)
            vector_rank = vector_ranks.get(chunk_id)
            score = sum(
                1 / (self._rrf_k + rank)
                for rank in (lexical_rank, vector_rank)
                if rank is not None
            )
            scored.append((score, chunk_id, record, lexical_rank, vector_rank))
        scored.sort(key=lambda item: (-item[0], item[1]))

        return [
            RetrievalResult(
                chunk_id=record.chunk_id,
                source_title=record.source_title,
                source_url=record.source_url,
                publication_date=record.publication_date,
                locator=record.locator,
                content=record.content,
                content_hash=record.content_hash,
                tags=record.tags,
                lexical_rank=lexical_rank,
                vector_rank=vector_rank,
                rrf_score=score,
            )
            for score, _, record, lexical_rank, vector_rank in scored[:top_k]
        ]
