"""Story audience, frames, polls and reactions. Post filters, collabs, pinning and time capsules.

Revision ID: 0007
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("""
        ALTER TABLE stories
          ADD COLUMN audience varchar(14) NOT NULL DEFAULT 'everyone',
          ADD COLUMN frame varchar(12),
          ADD COLUMN sticker jsonb
    """)
    conn.exec_driver_sql("""
        CREATE TABLE close_friends (
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          friend_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          created_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, friend_id)
        )
    """)
    conn.exec_driver_sql("""
        CREATE TABLE story_reactions (
          story_id uuid NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          emoji varchar(8) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (story_id, user_id)
        )
    """)
    conn.exec_driver_sql("""
        CREATE TABLE story_answers (
          story_id uuid NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          option integer NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (story_id, user_id)
        )
    """)
    conn.exec_driver_sql("ALTER TABLE post_media ADD COLUMN edit jsonb")
    conn.exec_driver_sql("ALTER TABLE posts ADD COLUMN pinned_at timestamptz, ADD COLUMN is_capsule boolean NOT NULL DEFAULT false")
    conn.exec_driver_sql("CREATE INDEX ix_posts_pinned ON posts (author_id, pinned_at) WHERE pinned_at IS NOT NULL")
    conn.exec_driver_sql("""
        CREATE TABLE post_collabs (
          post_id uuid PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          status varchar(10) NOT NULL DEFAULT 'pending',
          created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    conn.exec_driver_sql("CREATE INDEX ix_post_collabs_user ON post_collabs (user_id, status)")


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("DROP TABLE post_collabs")
    conn.exec_driver_sql("ALTER TABLE posts DROP COLUMN is_capsule, DROP COLUMN pinned_at")
    conn.exec_driver_sql("ALTER TABLE post_media DROP COLUMN edit")
    for table in ("story_answers", "story_reactions", "close_friends"):
        conn.exec_driver_sql(f"DROP TABLE {table}")
    conn.exec_driver_sql("ALTER TABLE stories DROP COLUMN sticker, DROP COLUMN frame, DROP COLUMN audience")
