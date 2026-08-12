"""CLI for idempotently ingesting a frozen evidence manifest."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.db import dispose_engine, get_session_factory
from app.evidence import ingest_corpus


async def _run(manifest_path: Path) -> None:
    result = await ingest_corpus(get_session_factory(), manifest_path)
    action = "created" if result.created else "already-current"
    print(
        f"Evidence corpus {result.corpus_version}: {action}; "
        f"chunks={result.chunk_count}; hash={result.corpus_hash}"
    )
    await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    asyncio.run(_run(args.manifest))


if __name__ == "__main__":
    main()
