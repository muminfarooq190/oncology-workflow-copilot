"""Add frozen evidence corpora and pgvector hybrid retrieval."""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260812_0002"
down_revision: str | None = "20260812_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "evidence_corpora",
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("manifest_hash", sa.String(length=71), nullable=False),
        sa.Column("corpus_hash", sa.String(length=71), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("embedding_provider", sa.String(length=128), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("version"),
    )
    op.create_table(
        "evidence_chunks",
        sa.Column("chunk_id", sa.String(length=128), nullable=False),
        sa.Column("corpus_version", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("source_title", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("publication_date", sa.Date(), nullable=False),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=71), nullable=False),
        sa.Column("license_status", sa.String(length=128), nullable=False),
        sa.Column("tumor_type", sa.String(length=64), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=256), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(source_title, '')), 'A') || "
                "setweight(to_tsvector('english', coalesce(content, '')), 'B')",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["corpus_version"], ["evidence_corpora.version"]),
        sa.PrimaryKeyConstraint("chunk_id"),
    )
    op.create_index(
        "ix_evidence_chunks_corpus_tumor",
        "evidence_chunks",
        ["corpus_version", "tumor_type"],
    )
    op.create_index(
        "ix_evidence_chunks_search_vector",
        "evidence_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.execute(
        "CREATE INDEX ix_evidence_chunks_embedding_hnsw ON evidence_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_evidence_chunks_embedding_hnsw")
    op.drop_index("ix_evidence_chunks_search_vector", table_name="evidence_chunks")
    op.drop_index("ix_evidence_chunks_corpus_tumor", table_name="evidence_chunks")
    op.drop_table("evidence_chunks")
    op.drop_table("evidence_corpora")
