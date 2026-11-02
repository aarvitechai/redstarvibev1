"""Record when a report was resolved, so the dashboard can show response time.

Revision ID: 0005
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE reports ADD COLUMN resolved_at timestamptz")
    conn.exec_driver_sql("CREATE INDEX ix_reports_created ON reports (created_at)")
    conn.exec_driver_sql("CREATE INDEX ix_audit_log_action ON audit_log (action, id)")


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("DROP INDEX ix_audit_log_action")
    conn.exec_driver_sql("DROP INDEX ix_reports_created")
    conn.exec_driver_sql("ALTER TABLE reports DROP COLUMN resolved_at")
