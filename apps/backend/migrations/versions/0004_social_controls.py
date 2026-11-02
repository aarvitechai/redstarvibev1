"""Mute, restrict, hidden words, held comments and people tagged in posts.

Revision ID: 0004
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("""
        CREATE TABLE user_limits (
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          target_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          kind varchar(10) NOT NULL CHECK (kind IN ('mute', 'restrict')),
          created_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, target_id, kind)
        )
    """)
    conn.exec_driver_sql("""
        CREATE TABLE post_tags (
          post_id uuid NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          PRIMARY KEY (post_id, user_id)
        )
    """)
    conn.exec_driver_sql("CREATE INDEX ix_post_tags_user ON post_tags (user_id, post_id DESC)")
    conn.exec_driver_sql("ALTER TABLE profiles ADD COLUMN hidden_words text[] NOT NULL DEFAULT '{}'")
    conn.exec_driver_sql("ALTER TABLE comments ADD COLUMN held boolean NOT NULL DEFAULT false")


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE comments DROP COLUMN held")
    conn.exec_driver_sql("ALTER TABLE profiles DROP COLUMN hidden_words")
    conn.exec_driver_sql("DROP TABLE post_tags")
    conn.exec_driver_sql("DROP TABLE user_limits")
