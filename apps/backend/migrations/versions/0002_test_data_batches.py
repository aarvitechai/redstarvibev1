"""Tracked test data batches. Every test account points at its batch, so removal can never touch real accounts.

Revision ID: 0002
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("""
        CREATE TABLE test_data_batches (
          id uuid PRIMARY KEY,
          label varchar(80) NOT NULL,
          status varchar(12) NOT NULL DEFAULT 'creating',
          error varchar(300),
          params jsonb NOT NULL,
          user_count integer NOT NULL DEFAULT 0,
          post_count integer NOT NULL DEFAULT 0,
          created_by uuid REFERENCES users(id) ON DELETE SET NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          removed_at timestamptz
        )
    """)
    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN test_batch_id uuid REFERENCES test_data_batches(id)")
    conn.exec_driver_sql("CREATE INDEX ix_users_test_batch ON users (test_batch_id) WHERE test_batch_id IS NOT NULL")
    conn.exec_driver_sql("CREATE INDEX ix_users_role ON users (role) WHERE role <> 'user'")


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE users DROP COLUMN test_batch_id")
    conn.exec_driver_sql("DROP TABLE test_data_batches")
