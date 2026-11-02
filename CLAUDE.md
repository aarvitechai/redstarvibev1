# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Response rules

Apply these to every response: code, explanation, and discussion.

| Rule | Meaning |
|---|---|
| No over-explain | Get to the point. Skip extra background. |
| Simple words | Use easy words. Avoid heavy jargon. |
| Hinglish in chat | Chat replies use a Hindi + English mix. |
| English in the repo | Every file in the repo stays in English. |
| No long paragraphs | Break the answer into short pieces. |
| Points and tables | Use bullets or tables. |
| Proper spacing | Leave space between lines. Do not pack text together. |
| Crisp | Say only what is needed. |
| No em-dashes | Do not use an em-dash. Use a comma or a period. |

## Project

RedStarVibe is a photo and video social platform. `docs/RedStarVibe_Technical_Architecture.md` is the spec. `docs/STATUS.md` records what is verified, what is written but never run, and where the build deliberately differs from the spec. Keep it honest when you change those things. Design decisions are in `docs/adr/`.

## Commands

The stack runs in Docker. Backend code is baked into images with no source mounts, so **backend and web changes need a rebuild** (`make up`) to show at http://localhost:8080.

```bash
python scripts/bootstrap_env.py   # first run only: writes .env with fresh secrets
make up                           # build and start everything; runs migrations
make seed                         # demo accounts and posts
make logs / make down

make test       # backend tests (see the warning below)
make lint       # ruff and mypy, in the test image
make test-web   # vitest, tsc, eslint (run npm install in apps/web first)
make e2e        # Playwright at 360, 768 and 1280 px; needs a running, seeded stack
make types      # regenerate packages/api-types from the OpenAPI schema
make load       # k6 baseline
```

Single tests:

```bash
# Backend, with the same variables as `make test`. Tests are copied into the image, so rebuild first.
docker build -q -t rsv-test --target test apps/backend
. ./.env; docker run --rm --network redstarvibe_internal -e APP_ENV=test -e BREACHED_PASSWORD_CHECK=false \
  -e DATABASE_URL=postgresql+asyncpg://rsv:$POSTGRES_PASSWORD@pgbouncer:5432/redstarvibe -e REDIS_URL=redis://redis:6379/0 \
  -e JWT_SECRET=testsecrettestsecrettestsecrettestsecret rsv-test python -m pytest -q tests/integration/test_auth.py -k login

# Web (from apps/web)
npx vitest run tests/unit/utils.test.ts
npx playwright test tests/e2e/admin.spec.ts --project=desktop-1280
```

**`make test` uses the same database as the running app.** Tests leave users behind, and `test_test_data.py` exercises "remove all", which can leave real test batches stuck in "removing" because the enqueue is mocked. Don't run it against data you want to keep.

**Run `docker compose` from PowerShell on Windows, or with `MSYS_NO_PATHCONV=1` in Git Bash.** If you `export` `.env` in Git Bash first, it rewrites `MEDIA_PUBLIC_BASE=/rsv-public` to a Windows path and every image breaks. Post JSON cached in Redis keeps the bad URL for up to 10 minutes.

Migrations live in `apps/backend/migrations/versions`, numbered by hand. The `migrate` service applies them on `make up`. Alembic connects directly to Postgres through `MIGRATIONS_DATABASE_URL`.

## Architecture

**One backend image, several processes** (`infra/docker/docker-compose.yml`): `api` (gunicorn), `ws` (uvicorn, same `app.main:app`), `mcp` (`app.mcp.server:app`), `worker` (Celery, queues `default,media,ai`), `beat`. The nginx `gateway` is the only entry point: `/api/` to api, `/ws` to ws, `/mcp` to mcp, `/rsv-raw/` and `/rsv-public/` to object storage, everything else to Next.js. A new top-level path must be added in `infra/docker/nginx/nginx.conf`.

**Backend modules** (`apps/backend/app/modules/<name>/`) each follow `router.py` → `service.py` → `repository.py`, with `schemas.py` and `models.py`. Wiring a new module means:
- including its router in `app/api/v1/router.py`
- importing its models in `app/models.py`, so SQLAlchemy and Alembic see them
- adding any Celery task file to `include` in `app/workers/celery_app.py`

**Side effects go through events.** Services commit, then call `app.core.events.emit("post.published", ...)`. `app/workers/event_tasks.py` holds the single dispatcher, which handles notifications, feed fan-out, and AI ingestion, so new reactions don't change the emitting module. Direct jobs use `enqueue(task, *args, queue=...)`. Both stringify their arguments.

**Database access:**
- The app connects through PgBouncer in transaction mode, so asyncpg statement caches stay off (ADR 0002). Don't rely on session state or named prepared statements.
- `likes` is hash partitioned and has no foreign keys (ADR 0003), so deleting users or posts must clear likes explicitly. See `purge()` in `app/modules/users/repository.py`, which also corrects other users' counters.

**Feed:** fan-out on write to Redis, except authors above `celebrity_threshold`, who are merged on read. Post counters are buffered and flushed to Postgres by beat every 5 seconds, so database values can lag briefly.

**Media:** browser uploads to a presigned URL, then `media.process_asset` checks magic bytes, re-encodes images to strip metadata (AVIF and WebP sizes), and builds an H.264 HLS ladder for video. Local storage is SeaweedFS and production is Cloudflare R2, using the same S3 code (ADR 0005).

**Auth:** cookies plus CSRF. Mutating requests need an `x-csrf-token` header matching the `rsv_csrf` cookie. Role checks are the `AdminUser` and `SuperAdminUser` dependencies in `app/api/deps.py`. Roles are `user`, `admin` and `superadmin`. Super admins can only be created with `scripts/make_superadmin.py`.

**Text on media:** `post_media.text_overlay` stores one text per photo or video as JSON, drawn by `TextOverlay.tsx` with percent positions and `cqw` font sizes. It is not burned into the pixels. Moderation and indexing must read `Post.full_text`, not `caption`.

**Search:** `modules/search` merges `posts.search_tsv` (keyword) and `posts.embedding` (pgvector) with RRF in `ranking.py`. Visibility runs in SQL. Only anonymous results are cached. `ai.index_post` and the nightly `ai.backfill_search` fill the columns. Models run on Cloudflare Workers AI (`app/ai/workers_ai.py`), never on this machine. `AI_PROVIDER` chooses `none`, `cloudflare` or `anthropic`.

**Test data** (`app/modules/admin/test_data.py`): generated accounts carry `users.test_batch_id` and are removed only by batch. They publish directly, skipping moderation and notifications. Seed accounts are not batches. The large demo set (`demo_data.py`) also links to the `demo` and `owner` seed accounts. Only a super admin can disable or delete it. Disabling sets its users' status to `disabled`, and visibility rules do the rest. While it exists, `make test` fails with `demo_exists` and can leave it stuck, so run backend tests against a separate database.

**Optional features degrade when unconfigured.** The Claude model client is `app/ai/llm_client.py`. `ANTHROPIC_API_KEY`, the `--extra ai` build, Google sign in, Turnstile and ClamAV are all optional, and the README lists what each does without configuration. Without a key, images are not moderated. `Settings` in `app/core/config.py` refuses to start in staging or production with weak secrets.

**Frontend** (`apps/web`, Next.js 16):
- `src/proxy.ts` (Next's replacement for `middleware.ts`) sets a strict per-request CSP nonce. Inline scripts or new third-party origins must fit that policy.
- `(main)` holds logged-in pages and `(auth)` the login flows. `/`, `/business/[slug]` and `/p/` work without login.
- API types come from `@rsv/api-types`, generated from `packages/api-types/openapi.json`. After changing a backend schema, run `make types` and alias new types in `src/lib/api/types.ts`. CI fails if the committed `openapi.json` is out of date.
- The UI is hand-written primitives, not shadcn. Images use `<picture>` with pre-sized variants, not `next/image`.
- `public/home/*` is generated by `scripts/generate_home_media.py`.

## Conventions

- Ruff line length is 130. mypy is strict on `app/` (not tests, scripts or migrations).
- CI (`.github/workflows/ci.yml`) requires 60% backend coverage on `app/modules`.
- Integration tests use real Postgres and Redis over `httpx.ASGITransport`. Use the `make_user` and `make_post` fixtures in `tests/conftest.py`. `make_post` skips the media worker.
- Writing long multi-file content through Bash heredocs breaks on apostrophes on this Windows setup. Use the Write tool.
