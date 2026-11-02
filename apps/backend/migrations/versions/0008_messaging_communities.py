"""Message requests, posts shared into chats, and communities.

Revision ID: 0008
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE conversation_members ADD COLUMN state varchar(10) NOT NULL DEFAULT 'active'")
    conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN post_id uuid")
    conn.exec_driver_sql("""
        CREATE TABLE communities (
          id uuid PRIMARY KEY,
          slug varchar(60) NOT NULL UNIQUE,
          name varchar(80) NOT NULL,
          description varchar(500) NOT NULL DEFAULT '',
          owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    conn.exec_driver_sql("CREATE INDEX ix_communities_name_trgm ON communities USING gin (name gin_trgm_ops)")
    conn.exec_driver_sql("""
        CREATE TABLE community_members (
          community_id uuid NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          created_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (community_id, user_id)
        )
    """)
    conn.exec_driver_sql("CREATE INDEX ix_community_members_user ON community_members (user_id)")
    conn.exec_driver_sql("""
        CREATE TABLE community_posts (
          id uuid PRIMARY KEY,
          community_id uuid NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
          author_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          body varchar(4000) NOT NULL DEFAULT '',
          asset_id uuid REFERENCES media_assets(id) ON DELETE SET NULL,
          deleted_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    conn.exec_driver_sql("CREATE INDEX ix_community_posts_list ON community_posts (community_id, id DESC) WHERE deleted_at IS NULL")


def downgrade() -> None:
    conn = op.get_bind()
    for table in ("community_posts", "community_members", "communities"):
        conn.exec_driver_sql(f"DROP TABLE {table}")
    conn.exec_driver_sql("ALTER TABLE messages DROP COLUMN post_id")
    conn.exec_driver_sql("ALTER TABLE conversation_members DROP COLUMN state")
