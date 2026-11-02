# 0006: Search runs on Postgres, with Cloudflare Workers AI for optional AI

Accepted. Keyword search uses `tsvector` with the `simple` config, because Postgres has no Hindi stemmer and `simple` treats every script the same. `pg_trgm` forgives typos. Semantic search uses pgvector with `bge-m3`, merged with keyword results by Reciprocal Rank Fusion.

We did not add Typesense, because the stack already runs Postgres and a second search store means a second thing to keep in sync and back up.

We first planned local models on Ollama. Their downloads filled the development machine's disk, so models now run on Workers AI and nothing is stored locally. The cost is that post text and photos leave our server, and the free daily allowance can run out. When it does, search falls back to keyword results.

Vectors are written and read through the pgvector SQLAlchemy type as text, not a registered asyncpg codec, so they stay safe under PgBouncer transaction mode (ADR 0002).
