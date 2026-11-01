# 0002: The app connects through PgBouncer, migrations connect directly

Accepted. PgBouncer in transaction mode cannot keep named prepared statements, so the asyncpg statement caches are off and
statement names are unique. Alembic uses `MIGRATIONS_DATABASE_URL` to reach Postgres directly.
