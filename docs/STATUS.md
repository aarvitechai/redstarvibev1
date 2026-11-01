# Implementation status

Measured against `RedStarVibe_Technical_Architecture.md`. "Verified" means exercised by an automated test against the real
running stack. "Written, not run" means the code or config exists but nothing has executed it yet.

## Verified

- Sign up with emailed code, password login, email code login, TOTP, rotating refresh tokens with reuse detection, CSRF
- Profiles, private accounts, follow requests, blocks, reports, data export, account deletion and purge
- Photo posts through the real pipeline: presigned upload, magic byte check, metadata stripped by re-encoding, AVIF and WebP sizes
- Video through the real pipeline: H.264 HLS ladder and poster, playback confirmed in Chromium
- Feed (fan-out on write, celebrity merge on read, ranking), likes, comments, replies, saves, collections, search
- Real-time chat with typing, delivered and seen; live like counters; notifications over WebSocket
- 1:1 video call through a real LiveKit server, video flowing both ways (with Chromium fake cameras)
- MCP server: OAuth 2.1 with PKCE, 7 tools, scope enforcement (`scripts/verify_mcp.py`)
- Vibe AI retrieval with tenant isolation, answering by quoting sources
- Responsive layout at 360, 768 and 1280 px, no horizontal scroll, 44 px touch targets on the mobile nav, strict CSP

## Written, not run

These need something this machine did not have.

| Item | What it needs |
|---|---|
| Claude features: auto captions, LLM moderation, generated assistant answers, LLM insights | `ANTHROPIC_API_KEY` |
| BGE-M3, OpenCLIP, faster-whisper | Image built with `--extra ai`, plus model downloads |
| Google sign in, Turnstile | Credentials |
| Web push delivery | HTTPS and a real browser push service. Subscribing code and sending code exist. |
| Cloudflare R2, LiveKit Cloud, real SMTP | Accounts. The same S3, LiveKit and SMTP code paths are exercised against local stand-ins. |
| GitHub Actions, Terraform, Helm, Argo CD, staging and production deploy | A GitHub repo, cloud accounts and a cluster |
| ClamAV scanning, Prometheus, Grafana and Loki profiles | `--profile av`, `--profile monitoring` |

Also not exercised in a browser test: stories viewer, group calls, audio calls, live streaming, reels feed scrolling, admin actions,
MCP write tools, draft and schedule flow. Their API rules are partly covered by the backend tests.

## Not built, or built differently from the guide

| Guide | This build | Why |
|---|---|---|
| Passkeys (WebAuthn) | Not built. TOTP only. | Scope |
| Phone OTP, Apple sign in | Not built | The guide marks these "later" |
| Separate admin app with SSO | `/admin` page in the main app, with role check, IP allow list and required MFA in production | Scope. No SSO. |
| Live streaming via LiveKit Egress to HLS | Viewers join the LiveKit room directly, subscribe only | Egress is a heavy extra service. This will not scale to large audiences. |
| Recording to R2, end to end encrypted calls | Not built | Opt in features in the guide |
| LlamaIndex, BGE reranker, Ragas evaluation | Direct hybrid search with reciprocal rank fusion, no reranker, no RAG evaluation in CI | See ADR 0004 |
| scikit-learn or XGBoost spam model, weekly retraining | Hand weighted score, computed once at sign up. Nothing acts on it yet. | Needs labelled data |
| Vision classifier for moderation | Rules plus Claude when a key is set. **Without a key, images are not moderated.** | Set a key before accepting public uploads |
| Known abuse hash matching | The check and table exist, but the table is empty | Needs a vetted provider such as PhotoDNA or NCMEC, which requires an application |
| Feature flags (Unleash or GrowthBook), product analytics (PostHog), uptime monitor | Not built | Scope |
| Qdrant, Kafka, OpenSearch, Citus, ScyllaDB | Not built | The guide schedules these for Phase 3 and later |
| shadcn/ui, next/image, list virtualization | Hand written primitives in the same style, `<picture>` with pre-sized variants, CSS `content-visibility` | Smaller bundle |
| Testcontainers | Tests run against the compose stack or CI service containers | Simpler on Windows |
| `likes` time partitioned | Hash partitioned | See ADR 0003 |
| MinIO or R2 locally | SeaweedFS | See ADR 0005 |

## Targets

Measured on one development laptop with every service on the same machine under Docker Desktop. These are not production numbers.

Re-measure on staging with `make load`.

| Target | Result |
|---|---|
| Feed API p95 under 200 ms | 231 ms at about 50 requests per second with 20 virtual users, 0 errors. **Missed.** |
| 1,000 requests per second baseline on staging | Not measured. Needs staging hardware. |
| Initial JS under 170 KB gzip | Feed 172 KB, login 187 KB. Slightly over. |
| Service test coverage 80% | 67% across `app/modules` |

LCP, INP and CLS have not been measured on a real 4G device.
