from sqlalchemy import text

from app import models  # noqa: F401
from app.core.database import Base, SessionLocal


async def test_orm_columns_exist_in_migrated_schema():
    async with SessionLocal() as s:
        rows = await s.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'"
        ))
        actual = {(a, b) for a, b in rows}
    expected = {(t.name, c.name) for t in Base.metadata.tables.values() for c in t.columns}
    assert expected - actual == set()


async def test_large_tables_are_partitioned():
    async with SessionLocal() as s:
        rows = await s.execute(text("SELECT relname FROM pg_class WHERE relkind = 'p'"))
        partitioned = set(rows.scalars())
    assert {"likes", "messages", "notifications"} <= partitioned
