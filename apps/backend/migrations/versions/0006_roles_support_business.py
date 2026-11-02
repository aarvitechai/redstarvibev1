"""Staff and business roles, support tickets, verification, plans, ad requests and business staff.

Revision ID: 0006
"""
from alembic import op
from sqlalchemy import text

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

PLANS = [
    ("free", "Free", "Basic features", 1),
    ("premium", "Premium", "No ads, verified badge, advanced editing", 2),
    ("creator", "Creator", "Tips, subscriptions, advanced analytics", 3),
    ("business", "Business", "Booking button, analytics, many service listings", 4),
    ("enterprise", "Enterprise", "Many staff accounts, dedicated support", 5),
]


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN verified boolean NOT NULL DEFAULT false")
    conn.exec_driver_sql("ALTER TABLE reports ADD COLUMN escalated_by uuid, ADD COLUMN escalated_at timestamptz")
    conn.exec_driver_sql("""
        CREATE TABLE tickets (
          id uuid PRIMARY KEY,
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          subject varchar(120) NOT NULL,
          status varchar(12) NOT NULL DEFAULT 'open',
          escalated_by uuid,
          resolved_by uuid,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    conn.exec_driver_sql("CREATE INDEX ix_tickets_user ON tickets (user_id, id DESC)")
    conn.exec_driver_sql("CREATE INDEX ix_tickets_status ON tickets (status, id)")
    conn.exec_driver_sql("""
        CREATE TABLE ticket_messages (
          id uuid PRIMARY KEY,
          ticket_id uuid NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
          author_id uuid REFERENCES users(id) ON DELETE SET NULL,
          is_staff boolean NOT NULL DEFAULT false,
          body varchar(4000) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    conn.exec_driver_sql("CREATE INDEX ix_ticket_messages_ticket ON ticket_messages (ticket_id, id)")
    conn.exec_driver_sql("""
        CREATE TABLE verification_requests (
          id uuid PRIMARY KEY,
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          kind varchar(10) NOT NULL CHECK (kind IN ('person', 'business')),
          details varchar(1000) NOT NULL,
          status varchar(10) NOT NULL DEFAULT 'pending',
          reason varchar(300),
          reviewed_by uuid,
          reviewed_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    conn.exec_driver_sql("CREATE UNIQUE INDEX ux_verification_pending ON verification_requests (user_id) WHERE status = 'pending'")
    conn.exec_driver_sql("""
        CREATE TABLE plans (
          code varchar(20) PRIMARY KEY,
          name varchar(40) NOT NULL,
          includes varchar(300) NOT NULL,
          price_paise integer CHECK (price_paise IS NULL OR price_paise >= 0),
          active boolean NOT NULL DEFAULT true,
          position integer NOT NULL DEFAULT 0
        )
    """)
    for code, name, includes, position in PLANS:
        conn.execute(
            text("INSERT INTO plans (code, name, includes, position) VALUES (:c, :n, :i, :p)"),
            {"c": code, "n": name, "i": includes, "p": position},
        )
    conn.exec_driver_sql("""
        CREATE TABLE ad_requests (
          id uuid PRIMARY KEY,
          business_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          post_id uuid NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
          headline varchar(80) NOT NULL,
          city varchar(80),
          daily_budget_paise integer NOT NULL CHECK (daily_budget_paise > 0),
          status varchar(10) NOT NULL DEFAULT 'pending',
          reason varchar(300),
          reviewed_by uuid,
          reviewed_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    conn.exec_driver_sql("CREATE INDEX ix_ad_requests_status ON ad_requests (status, id)")
    conn.exec_driver_sql("""
        CREATE TABLE business_staff (
          business_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          created_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (business_id, user_id)
        )
    """)


def downgrade() -> None:
    conn = op.get_bind()
    for table in ("business_staff", "ad_requests", "plans", "verification_requests", "ticket_messages", "tickets"):
        conn.exec_driver_sql(f"DROP TABLE {table}")
    conn.exec_driver_sql("ALTER TABLE reports DROP COLUMN escalated_at, DROP COLUMN escalated_by")
    conn.exec_driver_sql("ALTER TABLE users DROP COLUMN verified")
