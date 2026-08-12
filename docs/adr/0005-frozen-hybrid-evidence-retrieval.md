# ADR 0005: Freeze evidence and fuse lexical and vector ranks

- Status: Accepted
- Date: 2026-08-12

## Context

Tumor-board drafts need traceable evidence retrieval that can be reproduced during evaluation and audit. Live web search, mutable source snapshots, or unversioned embeddings make failures difficult to reconstruct. Lexical retrieval is strong for exact biomarkers and drug names, while vector retrieval can recover paraphrases; either method alone has predictable blind spots.

## Decision

Evidence is ingested only from a frozen manifest. Every chunk records immutable source metadata and a content hash, and the manifest fixes the corpus hash, embedding provider and dimensions, retrieval configuration, and freeze timestamp. Reusing a corpus version with different content fails closed.

PostgreSQL is the retrieval store. It creates one candidate list with weighted English full-text search and another with pgvector cosine distance. Reciprocal-rank fusion combines the two ranked lists using `k=60`. Responses retain component ranks and source metadata so a clinician can inspect why a result appeared.

Week 8 uses `clinical-hash-embedding-v1`, a deterministic 256-dimensional feature-hash baseline. This supports offline, zero-cost, repeatable CI but is explicitly not a clinically validated semantic model. Any replacement requires a new provider identifier, a newly frozen corpus version, and a comparison against the versioned evaluation suite.

## Consequences

- A retrieval result can be reconstructed from repository-owned artifacts and database configuration.
- Exact medical terms and paraphrases contribute independently to ranking.
- Corpus or embedding changes cannot silently alter historical evaluation results.
- The small development corpus and engineering labels do not establish clinical usefulness; clinician adjudication and a stronger production embedding remain launch blockers.
- Publication-date monitoring and corpus refresh policy are required before a hosted clinical pilot.
