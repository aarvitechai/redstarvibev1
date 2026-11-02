"""Post search columns: text, full text vector and embedding. Existing posts get keyword search straight away.

Revision ID: 0009
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("""
        ALTER TABLE posts
          ADD COLUMN search_text text,
          ADD COLUMN search_tsv tsvector,
          ADD COLUMN embedding vector(1024),
          ADD COLUMN embedding_model text,
          ADD COLUMN indexed_at timestamptz
    """)
    conn.exec_driver_sql("""
        UPDATE posts p SET search_text = concat_ws(' ', p.caption, overlay.words, p.location)
        FROM (
          SELECT po.id, string_agg(m.text_overlay->>'text', ' ') AS words
          FROM posts po LEFT JOIN post_media m ON m.post_id = po.id GROUP BY po.id
        ) overlay
        WHERE overlay.id = p.id
    """)
    conn.exec_driver_sql("UPDATE posts SET search_tsv = to_tsvector('simple', search_text)")
    conn.exec_driver_sql("CREATE INDEX ix_posts_search_tsv ON posts USING gin (search_tsv)")
    conn.exec_driver_sql("CREATE INDEX ix_posts_search_trgm ON posts USING gin (search_text gin_trgm_ops)")
    conn.exec_driver_sql("CREATE INDEX ix_posts_embedding ON posts USING hnsw (embedding vector_cosine_ops)")
    conn.exec_driver_sql("DROP INDEX ix_posts_caption_fts")
    # Search vectors now live on posts. The embeddings table keeps only assistant content.
    conn.exec_driver_sql("DELETE FROM embeddings WHERE entity_type IN ('post', 'post_image')")


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("CREATE INDEX ix_posts_caption_fts ON posts USING gin (to_tsvector('simple', caption))")
    conn.exec_driver_sql("""
        ALTER TABLE posts
          DROP COLUMN indexed_at, DROP COLUMN embedding_model, DROP COLUMN embedding, DROP COLUMN search_tsv, DROP COLUMN search_text
    """)
