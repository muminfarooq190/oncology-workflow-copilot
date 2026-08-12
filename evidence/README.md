# Evidence corpus

`nsclc-v1` is a frozen, content-addressed corpus of 19 short original paraphrases linked to public NCI clinical information and FDA approval notices. It does not reproduce paid guideline text and must not be described as a substitute for current clinical guidance.

Each chunk carries a stable ID, exact source URL, publication date, locator, source class, tumor type, tags, licensing status, and SHA-256 content hash. `manifest.json` fixes the chunk count, corpus hash, embedding contract, and retrieval settings. Ingestion is idempotent; attempting to reuse `nsclc-v1` with a different manifest or corpus hash fails closed.

Regenerate and verify the frozen artifacts:

```bash
python scripts/freeze_evidence_corpus.py
python scripts/validate_repository.py
```

After the PostgreSQL migration, ingest the corpus with:

```bash
python -m app.evidence_ingest evidence/manifest.json
```

The deterministic hash embedding is an engineering baseline for reproducible CI, not a clinically validated semantic model. A production embedding change requires a new provider identifier, corpus version, and retrieval comparison report.
