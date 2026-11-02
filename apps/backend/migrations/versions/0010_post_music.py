"""Background music on a post: the id of one track from the app's own library.

Revision ID: 0010
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().exec_driver_sql("ALTER TABLE posts ADD COLUMN music varchar(30)")


def downgrade() -> None:
    op.get_bind().exec_driver_sql("ALTER TABLE posts DROP COLUMN music")
