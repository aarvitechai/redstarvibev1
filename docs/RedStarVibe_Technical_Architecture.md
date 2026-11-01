# RedStarVibe: Technical Architecture & Implementation Guide

**Domain:** redstarvibe.com
**Version:** 1.0
**Date:** 1 November 2026
**Status:** Approved baseline for implementation

---

## 1. Overview

RedStarVibe is a photo and video social platform. Users share posts, stories and reels, follow each other, chat, and make audio or video calls. AI features (smart feed, auto captions, subtitles, image search, moderation, AI assistant) are built in from the start.

### 1.1 Goals

| Goal | Target |
|---|---|
| Performance | API p95 under 200 ms, feed first paint under 1.5 s on 4G |
| Scalability | Start at 0 users on free infra, grow to millions without a rewrite |
| Security | OWASP Top 10 covered, encrypted data, least privilege everywhere |
| Maintainability | One clean modular backend, typed contracts, automated tests and CI/CD |
| Availability | 99.9% in Growth phase, 99.95% in Scale phase |
| Devices | Mobile, tablet and desktop from one responsive React app (PWA) |

### 1.2 Final Technology Decision

| Layer | Technology |
|---|---|
| Frontend | React 19 + Next.js (App Router) + TypeScript |
| Mobile and tablet | Same React app, fully responsive, installable PWA |
| Styling | Tailwind CSS + shadcn/ui |
| Backend | Python 3.12 + FastAPI (async) |
| Database | PostgreSQL 16 |
| Vector search | pgvector (Phase 1-2), Qdrant (Phase 3+) |
| Cache and pub/sub | Redis |
| Background jobs | Celery + Redis (Kafka added in Scale phase) |
| Media storage | Cloudflare R2 (S3 compatible) + Cloudflare CDN |
| Audio / video calls | LiveKit (WebRTC) |
| AI / RAG | LlamaIndex, Claude API, open-source embeddings, Whisper, CLIP |
| MCP | Official MCP Python SDK |
| Containers | Docker, Docker Compose (Phase 1), Kubernetes (Phase 3+) |
| CI/CD | GitHub Actions |
| Edge | Cloudflare DNS, SSL, WAF, DDoS protection |
| Observability | OpenTelemetry, Prometheus, Grafana, Loki, Sentry |

**Why one Python backend:** AI, RAG, MCP, Whisper and CLIP all have their best libraries in Python. Keeping API and AI in one language means one codebase, one set of models, and one team skill set. Heavy AI work runs in separate worker processes so the API stays fast.

---

## 2. Features

### 2.1 Core (MVP)

| Feature | Notes |
|---|---|
| Sign up / login | Email + OTP, Google OAuth, phone OTP later |
| Profile | Avatar, bio, posts grid, followers / following |
| Posts | Multi photo / video carousel, caption, hashtags, mentions, location |
| Feed | Following feed, infinite scroll |
| Likes, comments, replies | Real-time counters |
| Follow / unfollow | Public and private accounts, follow requests |
| Search | Users, hashtags, places |
| Notifications | In-app, web push |
| Save / collections | Bookmark posts |

### 2.2 Phase 2

| Feature | Notes |
|---|---|
| Stories | 24 hour expiry, viewers list, highlights |
| Reels | Short vertical video, HLS streaming |
| Direct messages | 1:1 and group chat, typing, seen, media |
| Audio / video calls | 1:1 and group via LiveKit |
| Explore | Personalised discovery grid |
| Live streaming | LiveKit egress to HLS |

### 2.3 AI Features

| Feature | Technology |
|---|---|
| Smart feed ranking | Embeddings + engagement signals + ranking model |
| Auto caption and hashtags | Claude API (vision) |
| Reel subtitles | Whisper (faster-whisper) |
| Image search ("sunset at beach") | CLIP embeddings in pgvector |
| Content moderation | Vision classifier + LLM review queue |
| Spam / fake account detection | scikit-learn / XGBoost model |
| AI assistant ("Vibe AI") | RAG over help docs and user's own content |
| Creator insights | LLM summary of post analytics |

---

## 3. High Level Architecture

### 3.1 System Diagram

```
                     Users (Mobile / Tablet / Desktop browser, PWA)
                                        |
                                        v
                 Cloudflare (DNS, SSL, WAF, DDoS, CDN, Rate limit)
                    |                   |                     |
                    v                   v                     v
           Next.js frontend     Cloudflare R2 (media)   LiveKit (WebRTC)
                    |
                    v
           Load Balancer (NGINX / Cloud LB / K8s Ingress)
                    |
        +-----------+-------------+------------------+
        |                         |                  |
        v                         v                  v
  FastAPI API pods       WebSocket gateway pods   MCP server pods
  (stateless, N copies)  (chat, live events)      (AI agent tools)
        |                         |                  |
        +------------+------------+------------------+
                     |
          +----------+-----------+----------------+
          v                      v                v
     Redis (cache,         PostgreSQL         Job queue
     sessions, pub/sub,    primary +          (Celery on Redis,
     rate limits)          read replicas      Kafka in Scale phase)
                           + pgvector               |
                                                    v
                                    Workers (CPU and GPU pools)
                                    - media: resize, transcode, HLS
                                    - ai: embeddings, Whisper, CLIP
                                    - moderation, notifications, feed fan-out
```

### 3.2 Request Flows

**Post upload**

1. Client asks API for a presigned upload URL.
2. Client uploads the file directly to R2 (API never handles large files).
3. Client calls `POST /posts` with media keys and caption.
4. API saves post as `processing` and pushes a job.
5. Media worker creates sizes (WebP / AVIF), video HLS ladder, thumbnail.
6. AI worker runs moderation, embeddings, captions, subtitles.
7. Post becomes `published`. Feed fan-out job runs. Followers get notified.

**Feed read**

1. API reads the user's precomputed feed IDs from Redis.
2. Missing post data is loaded in bulk from cache, then Postgres replica.
3. Ranking service reorders the top N items.
4. Response is cursor paginated. Images come from CDN.

**Call**

1. Caller requests a call. API checks block / privacy rules.
2. API issues short lived LiveKit tokens for both users.
3. Callee is notified over WebSocket and push.
4. Media flows peer to LiveKit SFU. API never touches media.

### 3.3 Architecture Style

- **Modular monolith first.** One FastAPI codebase split into clear domain modules (auth, users, posts, feed, chat, calls, ai, notifications). Each module owns its tables, services and routes.
- **Extract services only when needed.** Modules talk through service interfaces and events, so any module (for example `feed` or `ai`) can later become its own service with no change to callers.
- **Event driven side effects.** Likes, follows and posts emit domain events. Notifications, counters, feed fan-out and AI indexing react to events in workers.

---

## 4. Frontend (React)

### 4.1 Stack

| Concern | Choice |
|---|---|
| Framework | Next.js (App Router), React 19, TypeScript strict |
| Styling | Tailwind CSS, shadcn/ui, CSS variables for theme (light / dark) |
| Server state | TanStack Query (caching, infinite scroll, optimistic updates) |
| Client state | Zustand |
| Forms | React Hook Form + Zod |
| API client | Generated from FastAPI OpenAPI schema (openapi-typescript) |
| Real-time | Native WebSocket with reconnect + backoff |
| Video | hls.js |
| Calls | LiveKit React components |
| PWA | Service worker, offline shell, web push, install prompt |
| Testing | Vitest, React Testing Library, Playwright (E2E) |

### 4.2 Responsive Design (Mobile, Tablet, Desktop)

| Breakpoint | Width | Layout |
|---|---|---|
| Mobile | under 640 px | Bottom tab bar, full width feed, swipe stories |
| Tablet | 640 - 1023 px | Icon side rail, centered feed, 3 column grid |
| Desktop | 1024 px and above | Full side nav, feed + suggestions panel |

Rules:

- Mobile first CSS. Every screen is designed for 360 px width first.
- Touch targets at least 44 x 44 px.
- `next/image` with responsive `sizes`, AVIF / WebP, blur placeholder.
- Safe area insets for notched phones. Works in portrait and landscape.
- Accessibility: WCAG 2.2 AA, keyboard navigation, alt text (AI suggested).

### 4.3 Brand

| Token | Value |
|---|---|
| Primary (Star Red) | #C8102E |
| Primary dark | #9B0C23 |
| Background light | #FFFFFF |
| Background dark | #0B0B0F |
| Text | #111111 / #F5F5F5 |
| Logo | Red star with network nodes (`public/brand/logo.png`, `favicon.ico`) |

### 4.4 Performance Budget

| Metric | Target |
|---|---|
| LCP | under 2.5 s (4G mobile) |
| INP | under 200 ms |
| CLS | under 0.1 |
| Initial JS | under 170 KB gzip |

Techniques: server components, route level code splitting, lazy load below the fold, virtualized long lists, prefetch next page of feed, HTTP caching through CDN.

---

## 5. Backend (Python + FastAPI)

### 5.1 Stack

| Concern | Choice |
|---|---|
| Framework | FastAPI (async) |
| Server | Uvicorn workers under Gunicorn |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Settings | pydantic-settings (env based) |
| Auth | JWT (short access + rotating refresh), Argon2id password hashing, Authlib for OAuth |
| Jobs | Celery + Redis, Celery Beat for schedules |
| Real-time | FastAPI WebSockets + Redis pub/sub |
| Storage | boto3 (R2, S3 compatible) |
| Media | FFmpeg, Pillow / pyvips |
| AI | LlamaIndex, anthropic SDK, sentence-transformers, faster-whisper, open_clip |
| Calls | livekit-api (token and room management) |
| MCP | mcp (official Python SDK) |
| Lint / format / types | Ruff, mypy (strict) |
| Tests | pytest, pytest-asyncio, httpx, Testcontainers |
| Dependency manager | uv |

### 5.2 Layering (inside every module)

```
router.py      HTTP / WS endpoints. No business logic.
schemas.py     Pydantic request / response models.
service.py     Business rules. Calls repository and other services.
repository.py  All SQL. Returns domain objects.
models.py      SQLAlchemy tables.
events.py      Domain events this module emits.
tasks.py       Celery tasks this module owns.
```

Rule: routers call services, services call repositories. Nothing skips a layer.

### 5.3 API Standards

- REST, versioned under `/api/v1`.
- Cursor pagination (`?cursor=...&limit=20`), never offset on large tables.
- Consistent error body: `{ "error": { "code", "message", "request_id" } }`.
- Idempotency key header on create endpoints (posts, payments later).
- OpenAPI schema is the contract. Frontend types are generated from it.

---

## 6. Database (PostgreSQL)

### 6.1 Core Tables

| Table | Key columns |
|---|---|
| users | id (UUIDv7), username (unique, citext), email, password_hash, is_private, status, created_at |
| profiles | user_id, display_name, bio, avatar_key, website |
| follows | follower_id, followee_id, status (active / pending), created_at |
| posts | id, author_id, caption, visibility, status, like_count, comment_count, created_at |
| post_media | id, post_id, kind (image / video), r2_key, width, height, duration, position |
| likes | user_id, post_id, created_at (PK: user_id + post_id) |
| comments | id, post_id, author_id, parent_id, body, created_at |
| hashtags / post_hashtags | tag, post_id |
| stories | id, author_id, media_key, expires_at |
| conversations / messages | id, members, sender_id, body, media_key, created_at |
| notifications | id, user_id, type, actor_id, entity_id, read_at |
| blocks / reports | blocker_id, blocked_id / reporter_id, entity, reason, status |
| embeddings | entity_type, entity_id, model, vector (pgvector), updated_at |
| audit_log | actor_id, action, target, ip, created_at |

### 6.2 Database Rules

- UUIDv7 primary keys (time ordered, good for indexes and future sharding).
- Every foreign key and every `WHERE` / `ORDER BY` column used in hot paths is indexed.
- Counters (`like_count`) are updated asynchronously from Redis to avoid row lock contention.
- Soft delete (`deleted_at`) for user content, hard delete after retention window for privacy.
- Large tables (`likes`, `messages`, `notifications`) are partitioned by time from day one.
- PgBouncer in transaction mode in front of Postgres.
- All schema changes through Alembic, reviewed in PR, backward compatible (expand then contract).

### 6.3 Local Development

PostgreSQL runs in Docker for every developer (`docker compose up db`). The existing local SQL Server instance (`DESKTOP-2ERCDGB\MSSQLSERVER01`) is **not** used by this project, because pgvector and the Postgres features above are required.

---

## 7. Caching Strategy (Redis)

| Data | Pattern | TTL |
|---|---|---|
| Home feed IDs | Precomputed list per user (fan-out on write) | 7 days, trimmed to 800 |
| Post / user objects | Cache aside | 10 min |
| Like / view counters | Redis INCR, flushed to Postgres every few seconds | n/a |
| Sessions / refresh token denylist | Key value | token lifetime |
| Rate limit buckets | Sliding window | per window |
| Online presence | Key with heartbeat | 60 s |

Celebrity accounts (very large follower counts) use **fan-out on read** instead, merged at read time, to avoid writing millions of feed entries per post.

---

## 8. Media Pipeline

```
Client --presigned PUT--> R2 (raw/ bucket, private)
                           |
                     event -> queue
                           v
                    Media worker
          - validate type and size (magic bytes, not extension)
          - strip EXIF / GPS metadata
          - images: 320 / 640 / 1080 px, AVIF + WebP
          - video: H.264 HLS ladder 360p / 720p / 1080p, thumbnail, poster
          - virus / malware scan
                           v
                 R2 (public/ bucket) -> Cloudflare CDN -> users
```

Limits: images up to 20 MB, videos up to 90 s for reels and 10 min for posts (configurable).

---

## 9. Real-time: Chat, Notifications, Presence

- Dedicated WebSocket gateway pods (same FastAPI codebase, separate deployment).
- Each pod subscribes to Redis pub/sub channels for its connected users. Any pod can publish, so it scales horizontally.
- Messages are stored in Postgres first, then delivered. Client acks give "delivered" and "seen".
- Offline users get web push (VAPID) and later mobile push.
- Scale phase: Redis pub/sub replaced or backed by Kafka / NATS for durable fan-out.

---

## 10. Audio and Video Calling (LiveKit)

| Item | Decision |
|---|---|
| Media server | LiveKit SFU (open source, self host or LiveKit Cloud) |
| Signalling / auth | FastAPI issues short lived room tokens (5 min) |
| NAT traversal | LiveKit built in TURN |
| Group calls | Up to 8 video, 32 audio in v1 |
| Recording / live | LiveKit Egress to R2 (opt in only) |
| Encryption | DTLS-SRTP by default, end to end encryption option for 1:1 |

Phase 1 uses the LiveKit Cloud free plan. When minutes grow, self host LiveKit on our own servers.

---

## 11. AI and RAG Pipeline

### 11.1 RAG Flow

```
Sources: help center docs, policies, user's own posts / captions / comments
                 |
          domain event / schedule
                 v
       AI worker: clean -> chunk (500 tokens, 50 overlap) -> embed
                 v
       pgvector (Phase 1-2) / Qdrant (Phase 3+), with tenant filter user_id
                 v
Query -> embed -> hybrid search (vector + Postgres full text) -> rerank
                 v
        Claude API with retrieved context + guardrails -> answer with citations
```

| Part | Choice |
|---|---|
| Framework | LlamaIndex |
| Text embeddings | BGE-M3 (self hosted, multilingual incl. Hindi) or Voyage API |
| Image embeddings | OpenCLIP |
| Reranker | BGE reranker |
| LLM | Claude API |
| Evaluation | Ragas + a fixed golden question set run in CI |

### 11.2 AI Guardrails

- Users can only retrieve their own private content (filter by `user_id` at query time, never in the prompt alone).
- Prompt injection defence: retrieved text is wrapped as data, system prompt forbids tool use from retrieved text.
- PII redaction before sending text to external APIs.
- Per user AI quota and cost tracking.
- Every AI output that is published (captions, moderation decisions) is logged for review.

### 11.3 Model Serving

| Model | Where |
|---|---|
| Whisper, CLIP, BGE | GPU worker pool (CPU in Phase 1, slower but free) |
| Spam / ranking models | CPU workers, retrained weekly from feature tables |
| LLM | Claude API (no GPU needed) |

---

## 12. MCP Server

RedStarVibe exposes an MCP server so AI agents (for example Claude) can work with a user's account safely.

| Tool | Scope | Purpose |
|---|---|---|
| `search_posts` | read | Search user's and public posts (RAG) |
| `get_profile` | read | Profile and stats |
| `get_post_insights` | read | Reach, likes, comments for own posts |
| `draft_post` | write | Create a draft (never auto publish) |
| `schedule_post` | write | Schedule a draft, needs user confirm |
| `list_notifications` | read | Recent activity |
| `report_content` | write | File a moderation report |

Security for MCP:

- Streamable HTTP transport at `mcp.redstarvibe.com`.
- OAuth 2.1 with PKCE. User grants scopes (`read`, `write:drafts`).
- Every tool calls the same service layer as the REST API, so the same permission checks apply.
- Write tools are rate limited and audited. Destructive actions are not exposed.

---

## 13. Security

### 13.1 Identity and Access

| Control | Implementation |
|---|---|
| Passwords | Argon2id, breached password check, min 10 chars |
| Tokens | Access JWT 15 min, refresh token 30 days, rotated on use, stored in HttpOnly Secure SameSite cookie |
| MFA | TOTP and passkeys (WebAuthn) |
| OAuth | Google (later Apple), state + PKCE |
| Authorization | Policy checks in service layer (owner, follower, blocked, private) |
| Admin | Separate admin app, SSO + MFA, IP allow list, full audit log |

### 13.2 Application Security (OWASP Top 10)

| Risk | Defence |
|---|---|
| Injection | SQLAlchemy bound parameters only, no raw string SQL |
| XSS | React escaping, strict Content Security Policy, sanitized rich text |
| CSRF | SameSite cookies + CSRF token on cookie authenticated writes |
| Broken access control | Object level checks in every service method, tests for IDOR |
| SSRF | No user supplied URLs fetched server side without allow list |
| File upload | Presigned URLs with size / type limits, magic byte check, re-encode all media |
| Rate limiting | Cloudflare edge + Redis per user / per IP limits on login, OTP, posting, DMs |
| Bots / spam | Turnstile on sign up, spam model, account age limits |
| Secrets | Never in Git. Doppler / Vault / cloud secret manager. Rotated |
| Dependencies | Dependabot, `pip-audit`, `npm audit`, Trivy image scans in CI |
| Headers | HSTS, CSP, X-Content-Type-Options, Referrer-Policy, Permissions-Policy |

### 13.3 Data Protection

- TLS 1.2+ everywhere, including internal service traffic in Scale phase (mTLS via service mesh).
- Encryption at rest for Postgres, Redis snapshots and R2.
- Field level encryption for phone numbers and other sensitive PII.
- Location metadata stripped from uploaded media.
- Compliance: India DPDP Act 2023, GDPR ready (data export, account deletion within 30 days).
- Child safety: minimum age 13, report flows, known abuse hash matching on uploads.

### 13.4 Infrastructure Security

- Private network for database, Redis and workers. Only the load balancer is public.
- Least privilege IAM per service.
- SSH disabled on servers, access through bastion or SSM.
- WAF managed rules on Cloudflare.
- Daily encrypted backups, point in time recovery, restore tested monthly.

---

## 14. Performance

| Area | Technique |
|---|---|
| API | Async I/O, orjson responses, connection pooling, avoid N+1 (selectinload), response compression |
| Database | Right indexes, read replicas for reads, partitioning, EXPLAIN in PR for new hot queries |
| Cache | Redis for feed, objects, counters; HTTP cache headers for public data |
| Media | CDN, AVIF / WebP, HLS adaptive bitrate, lazy loading |
| Heavy work | Always in background workers, never in request path |
| Frontend | Server components, code splitting, prefetch, virtualization |

**Load testing:** k6 scripts in repo. Every release candidate must pass the baseline (for example 1,000 RPS on feed with p95 under 200 ms on staging).

---

## 15. Scalability

### 15.1 Principles

- **Stateless API.** No local session or file state. Any pod can serve any request.
- **Horizontal scaling.** Add pods behind the load balancer.
- **Async everything heavy.** Queues absorb spikes.
- **Data partitioning ready.** UUIDv7 keys, user scoped tables, so sharding by `user_id` is possible later.

### 15.2 Load Balancing

| Level | Tool |
|---|---|
| Global / edge | Cloudflare (geo routing, failover) |
| Regional | Cloud load balancer or NGINX (Phase 1) |
| Cluster | Kubernetes Ingress (NGINX), least connections |
| WebSockets | Sticky by connection, horizontal via Redis pub/sub |
| Database | PgBouncer + read replica routing |

### 15.3 Auto Scaling

- Kubernetes HPA on CPU and request rate for API pods.
- KEDA on queue length for worker pods (scale to zero for GPU workers when idle).
- Cluster autoscaler adds nodes.

### 15.4 Scaling Roadmap

| Phase | Users | Infrastructure | Approx cost |
|---|---|---|---|
| 1. Launch | 0 - 10K | One Oracle Cloud Always Free ARM VM (4 core, 24 GB), Docker Compose, Cloudflare free, R2 free, LiveKit Cloud free | Free |
| 2. Growth | 10K - 100K | 2-3 app servers, managed Postgres with replica, managed Redis, separate worker VM | Low |
| 3. Scale | 100K - 1M | Kubernetes, autoscaling, Qdrant, Kafka, GPU worker pool, OpenSearch | Medium |
| 4. Big brand | 1M+ | Multi region, Postgres sharding (Citus), ScyllaDB for messages / feed, dedicated ML platform | High |

Rule: move to the next phase only when metrics show the need (CPU above 70%, p95 rising, DB connections near limit).

---

## 16. Maintainability

| Practice | Detail |
|---|---|
| Monorepo | One repo, clear `apps/` and `packages/` folders |
| Typed contracts | Pydantic on backend, generated TypeScript types on frontend |
| Code style | Ruff + mypy strict (Python), ESLint + Prettier + TS strict (frontend) |
| Pre-commit hooks | Lint, format, secret scan before every commit |
| Tests | Unit (services), integration (Testcontainers Postgres / Redis), E2E (Playwright). Target 80% on services |
| Branching | Trunk based, short lived feature branches, PR review required |
| Commits | Conventional Commits, automated changelog |
| Feature flags | Unleash / GrowthBook, to ship safely and roll back without deploy |
| Docs | ADRs (Architecture Decision Records) in `docs/adr`, README per app, OpenAPI docs |
| Ownership | Each module has an owner in `CODEOWNERS` |

---

## 17. DevOps and CI/CD

### 17.1 Pipeline (GitHub Actions)

| Stage | Action |
|---|---|
| 1. Check | Lint, type check, secret scan |
| 2. Test | Unit + integration tests with Postgres and Redis containers |
| 3. Security | pip-audit, npm audit, Trivy, CodeQL |
| 4. Build | Docker images (multi stage, non root, arm64 + amd64), push to GHCR |
| 5. Deploy staging | Auto on merge to `main`, run migrations, smoke tests, k6 baseline |
| 6. Deploy production | Manual approval, rolling / canary, auto rollback on error rate rise |

### 17.2 Environments

| Env | Purpose |
|---|---|
| local | Docker Compose on developer machine |
| staging | Same as production, smaller size, test data |
| production | Live users |

### 17.3 Infrastructure as Code

- Terraform for cloud resources (VMs, DNS, R2 buckets, databases).
- Helm charts for Kubernetes apps (Phase 3+), deployed by ArgoCD (GitOps).

---

## 18. Observability

| Signal | Tool |
|---|---|
| Logs | Structured JSON (structlog) to Grafana Loki |
| Metrics | Prometheus + Grafana dashboards (RED: rate, errors, duration) |
| Traces | OpenTelemetry across frontend, API, workers |
| Errors | Sentry (frontend + backend) |
| Uptime | Uptime Kuma / Better Stack |
| Product analytics | PostHog (self hosted option) |

Alerts: p95 latency, 5xx rate above 1%, queue backlog, DB replication lag, disk above 80%, failed backups.

---

## 19. Folder Structure

```
redstarvibe/
├── apps/
│   ├── web/                              # React (Next.js) responsive PWA
│   │   ├── public/
│   │   │   ├── brand/                    # logo.png, logo.svg
│   │   │   ├── icons/                    # PWA icons 192, 512
│   │   │   ├── favicon.ico
│   │   │   └── manifest.webmanifest
│   │   ├── src/
│   │   │   ├── app/                      # routes
│   │   │   │   ├── (auth)/login/
│   │   │   │   ├── (auth)/signup/
│   │   │   │   ├── (main)/feed/
│   │   │   │   ├── (main)/explore/
│   │   │   │   ├── (main)/reels/
│   │   │   │   ├── (main)/messages/
│   │   │   │   ├── (main)/notifications/
│   │   │   │   ├── (main)/[username]/
│   │   │   │   ├── p/[postId]/
│   │   │   │   ├── call/[roomId]/
│   │   │   │   └── layout.tsx
│   │   │   ├── components/
│   │   │   │   ├── ui/                   # shadcn primitives
│   │   │   │   ├── layout/               # BottomNav, SideRail, SideNav
│   │   │   │   ├── post/
│   │   │   │   ├── story/
│   │   │   │   ├── reel/
│   │   │   │   ├── chat/
│   │   │   │   └── call/
│   │   │   ├── features/                 # feature logic (hooks + state)
│   │   │   │   ├── auth/
│   │   │   │   ├── feed/
│   │   │   │   ├── profile/
│   │   │   │   ├── chat/
│   │   │   │   └── ai-assistant/
│   │   │   ├── lib/
│   │   │   │   ├── api/                  # generated OpenAPI client
│   │   │   │   ├── ws/                   # websocket client
│   │   │   │   └── utils/
│   │   │   ├── hooks/
│   │   │   ├── stores/                   # Zustand
│   │   │   ├── styles/
│   │   │   └── sw/                       # service worker
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   └── e2e/
│   │   ├── Dockerfile
│   │   ├── next.config.ts
│   │   ├── tailwind.config.ts
│   │   └── package.json
│   │
│   └── backend/                          # Python FastAPI
│       ├── app/
│       │   ├── main.py                   # app factory
│       │   ├── core/
│       │   │   ├── config.py             # settings from env
│       │   │   ├── security.py           # hashing, JWT
│       │   │   ├── database.py           # async engine, session
│       │   │   ├── cache.py              # Redis client
│       │   │   ├── storage.py            # R2 client, presigned URLs
│       │   │   ├── events.py             # event bus
│       │   │   ├── logging.py
│       │   │   ├── telemetry.py          # OpenTelemetry
│       │   │   ├── rate_limit.py
│       │   │   └── errors.py
│       │   ├── api/
│       │   │   ├── deps.py               # auth, db session deps
│       │   │   └── v1/router.py          # mounts module routers
│       │   ├── modules/
│       │   │   ├── auth/
│       │   │   │   ├── router.py
│       │   │   │   ├── schemas.py
│       │   │   │   ├── service.py
│       │   │   │   ├── repository.py
│       │   │   │   ├── models.py
│       │   │   │   └── tasks.py
│       │   │   ├── users/
│       │   │   ├── follows/
│       │   │   ├── posts/
│       │   │   ├── media/
│       │   │   ├── feed/
│       │   │   ├── comments/
│       │   │   ├── stories/
│       │   │   ├── reels/
│       │   │   ├── chat/
│       │   │   ├── calls/
│       │   │   ├── notifications/
│       │   │   ├── search/
│       │   │   ├── moderation/
│       │   │   └── admin/
│       │   ├── ai/
│       │   │   ├── rag/
│       │   │   │   ├── ingest.py
│       │   │   │   ├── chunking.py
│       │   │   │   ├── retriever.py
│       │   │   │   └── generator.py
│       │   │   ├── embeddings/
│       │   │   ├── vision/               # CLIP, captioning
│       │   │   ├── speech/               # Whisper
│       │   │   ├── ranking/              # feed ranking model
│       │   │   ├── safety/               # moderation, PII redaction
│       │   │   └── llm_client.py
│       │   ├── realtime/
│       │   │   ├── gateway.py            # WebSocket endpoint
│       │   │   └── pubsub.py
│       │   ├── mcp/
│       │   │   ├── server.py
│       │   │   ├── auth.py               # OAuth 2.1
│       │   │   └── tools/
│       │   └── workers/
│       │       ├── celery_app.py
│       │       ├── media_tasks.py
│       │       ├── ai_tasks.py
│       │       ├── feed_tasks.py
│       │       └── notification_tasks.py
│       ├── migrations/                   # Alembic
│       ├── tests/
│       │   ├── unit/
│       │   ├── integration/
│       │   └── load/                     # k6 scripts
│       ├── Dockerfile
│       ├── pyproject.toml
│       └── uv.lock
│
├── packages/
│   └── api-types/                        # generated TS types from OpenAPI
│
├── infra/
│   ├── docker/
│   │   ├── docker-compose.yml            # local + Phase 1
│   │   ├── docker-compose.prod.yml
│   │   └── nginx/nginx.conf
│   ├── terraform/
│   │   ├── modules/
│   │   └── envs/{staging,production}/
│   ├── k8s/
│   │   ├── helm/redstarvibe/
│   │   └── argocd/
│   └── monitoring/
│       ├── prometheus/
│       ├── grafana/dashboards/
│       └── loki/
│
├── docs/
│   ├── architecture.md
│   ├── adr/                              # 0001-use-fastapi.md ...
│   ├── api/
│   ├── runbooks/                         # incident, restore, rotate secrets
│   └── security/
│
├── scripts/                              # dev helpers, seed data
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── deploy-staging.yml
│   │   └── deploy-prod.yml
│   ├── CODEOWNERS
│   └── dependabot.yml
├── .pre-commit-config.yaml
├── .env.example
├── Makefile
└── README.md
```

---

## 20. Free Hosting Plan (Phase 1)

| Need | Service |
|---|---|
| Domain DNS, SSL, CDN, WAF | Cloudflare (free) |
| Frontend | Cloudflare Pages, or same Oracle VM behind NGINX |
| Backend, Postgres, Redis, workers | Oracle Cloud Always Free ARM VM (4 OCPU, 24 GB RAM, 200 GB disk) |
| Photos and videos | Cloudflare R2 (10 GB free, no egress fees) |
| Calls | LiveKit Cloud free plan |
| CI/CD | GitHub Actions |
| Errors / analytics | Sentry free, PostHog free |

Domain setup: point `redstarvibe.com` nameservers to Cloudflare. Records: `redstarvibe.com` and `www` (web), `api.redstarvibe.com` (backend), `ws.redstarvibe.com` (realtime), `mcp.redstarvibe.com` (MCP), `media.redstarvibe.com` (R2 custom domain).

Note: free tiers have limits and terms that change. Recheck them before launch and set billing alerts once on paid plans.

---

## 21. Implementation Roadmap

| Sprint (2 weeks) | Deliverable |
|---|---|
| 1 | Monorepo, Docker Compose, CI, auth (signup, login, JWT, OAuth) |
| 2 | Profiles, follow system, media upload pipeline |
| 3 | Posts, feed (fan-out), likes, comments |
| 4 | Search, notifications, web push, PWA install |
| 5 | Hardening: rate limits, security headers, load test, deploy Phase 1 (MVP launch) |
| 6 | Stories, DMs (WebSocket) |
| 7 | Reels (HLS), Explore |
| 8 | Audio / video calls (LiveKit) |
| 9 | AI: embeddings, moderation, auto captions, Whisper subtitles |
| 10 | RAG assistant, MCP server, feed ranking v1 |

---

## 22. Definition of Done (every feature)

- Code reviewed and merged with passing CI.
- Unit and integration tests added.
- Authorization checks tested (including "other user's object").
- Works on mobile (360 px), tablet (768 px) and desktop (1280 px).
- Metrics, logs and error tracking in place.
- API documented in OpenAPI. ADR written if an architecture choice was made.
- Feature flag in place for risky changes.
