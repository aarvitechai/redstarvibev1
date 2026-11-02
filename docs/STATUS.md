# Implementation status

Measured against `RedStarVibe_Technical_Architecture.md`. "Verified" means exercised by an automated test against the real
running stack. "Written, not run" means the code or config exists but nothing has executed it yet.

## Verified

- Sign up with emailed code, password login, email code login, TOTP, rotating refresh tokens with reuse detection, CSRF
- Profiles, private accounts, follow requests, blocks, reports, data export, account deletion and purge
- Photo posts through the real pipeline: presigned upload, magic byte check, metadata stripped by re-encoding, AVIF and WebP sizes
- Video through the real pipeline: H.264 HLS ladder and poster, playback confirmed in Chromium
- Text on a photo or video while creating a post: style, size, colour, drag to place, shown on the published post and moderated with the caption
- Password reset by emailed code, which ends all sessions
- Mute, restrict and hidden words (held comments show only to their author and the post owner, who can allow them)
- Tagging people in posts, a Tagged tab on profiles, and removing your own tag
- Hashtag pages with Top and Recent; share by copy link, WhatsApp or the device share sheet
- View counts on photos, videos and reels: one per account or visitor cookie per post per day, not counting the author
- Admin and super admin dashboards, the full report list with filters and CSV export, and the audit log
- Staff and business roles from one permission map, support tickets, verification, plan prices and ad review
- Story close friends, reactions, polls, quizzes and festival frames
- Post filters (shown with CSS, the file is unchanged), collab posts, pinned posts and time capsules
- Message requests, sharing posts into chats, group chat screens, voice notes and communities
- Feed (fan-out on write, celebrity merge on read, ranking), likes, comments, replies, saves, collections, search
- Real-time chat with typing, delivered and seen; live like counters; notifications over WebSocket
- 1:1 video call through a real LiveKit server, video flowing both ways (with Chromium fake cameras)
- MCP server: OAuth 2.1 with PKCE, 7 tools, scope enforcement (`scripts/verify_mcp.py`)
- Vibe AI retrieval with tenant isolation, answering by quoting sources
- Large demo set on the real stack: 100 accounts, 20,000 posts, 20 short videos. Super admin disable, enable and delete through the API, with admins refused. Video playback in Chromium.
- Responsive layout at 360, 768 and 1280 px, no horizontal scroll, 44 px touch targets on the mobile nav, strict CSP

## Written, not run

These need something this machine did not have.

| Item | What it needs |
|---|---|
| Chat translation | `ANTHROPIC_API_KEY`. Tested with a stand-in for Claude only. |
| Claude features: auto captions, LLM moderation, generated assistant answers, LLM insights | `ANTHROPIC_API_KEY` |
| faster-whisper | Image built with `--extra ai`, plus a model download |
| Semantic and hybrid search, similar posts, writing helper, photo captions and tagline | `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_AI_TOKEN`. Tested with stand-ins for Cloudflare only. The photo request format has never been sent to the real model. |
| 30 golden search queries (`test_search_golden.py`) | Real Cloudflare keys in `GOLDEN_ACCOUNT` and `GOLDEN_TOKEN`. Skipped without them. |
| k6 search run (`tests/load/search.js`): p95 under 200 ms keyword, under 400 ms hybrid | A running stack and k6. Not measured. |
| Google sign in, Turnstile | Credentials |
| Web push delivery | HTTPS and a real browser push service. Subscribing code and sending code exist. |
| Cloudflare R2, LiveKit Cloud, real SMTP | Accounts. The same S3, LiveKit and SMTP code paths are exercised against local stand-ins. |
| GitHub Actions, Terraform, Helm, Argo CD, staging and production deploy | A GitHub repo, cloud accounts and a cluster |
| ClamAV scanning, Prometheus, Grafana and Loki profiles | `--profile av`, `--profile monitoring` |

The demo set has no capsules, drafts, calls, live streams, post filters or AI suggestions. Its 200 photos repeat across posts, and its stories expire after 24 hours. Disabling it hides posts, stories and profiles, but comments and chat messages from its accounts are not filtered.

Also not exercised in a browser test: disable and enable buttons, stories viewer, group calls, audio calls, live streaming, reels feed scrolling, admin actions,
MCP write tools, draft and schedule flow. Their API rules are partly covered by the backend tests.

## Known test failures

Run on 2026-11-02 against a fresh stack, with AI off.

| Test | Cause |
|---|---|
| `test_purge_removes_a_user_who_has_conversations_and_likes` under `make test` | `make test` does not pass `S3_ENDPOINT` or the S3 keys. Passes when they are set. |
| `search.spec.ts`, search page, at 360, 768 and 1280 px | Expects "deem" to find `demo`. Trigram similarity is 0.25, under the 0.3 limit. "deme" and "demoo" do find it, "dmeo" does not. |
| `search.spec.ts`, header search box | Expects a `travel` tag, but the seed data has no post with it. |
| `admin.spec.ts`, test data | Reads `users` from `/search`, which now returns `items` and needs `type=users`. |

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
| AI search plan: Ollama with `bge-m3` and Gemma, AI levels by server RAM | Cloudflare Workers AI with `bge-m3` and Llama. No model on this machine. Post text and photos go to Cloudflare. | See ADR 0006 |

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
