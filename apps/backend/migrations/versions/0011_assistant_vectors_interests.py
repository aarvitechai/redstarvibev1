"""Assistant vectors move to the same 1024 size as post search, and people can choose interests.

The old assistant vectors cannot be resized, so they are cleared. Run ai.ingest_help and ai.backfill_search afterwards to
rebuild them. Both also run nightly.

Revision ID: 0011
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _resize(size: int) -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("DELETE FROM embeddings")
    conn.exec_driver_sql("DROP INDEX ix_embeddings_vector")
    conn.exec_driver_sql(f"ALTER TABLE embeddings ALTER COLUMN vector TYPE vector({size})")
    conn.exec_driver_sql("CREATE INDEX ix_embeddings_vector ON embeddings USING hnsw (vector vector_cosine_ops)")


def upgrade() -> None:
    _resize(1024)
    op.get_bind().exec_driver_sql("ALTER TABLE profiles ADD COLUMN interests text[] NOT NULL DEFAULT '{}'")


def downgrade() -> None:
    op.get_bind().exec_driver_sql("ALTER TABLE profiles DROP COLUMN interests")
    _resize(512)
