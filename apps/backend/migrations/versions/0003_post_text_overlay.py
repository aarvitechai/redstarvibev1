"""Text shown on top of a post's photo or video.

Revision ID: 0003
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().exec_driver_sql("ALTER TABLE post_media ADD COLUMN text_overlay jsonb")


def downgrade() -> None:
    op.get_bind().exec_driver_sql("ALTER TABLE post_media DROP COLUMN text_overlay")
