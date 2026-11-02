# RedStarVibe: New Features

This file lists only **new features** to build on the existing stack. The stack, Docker setup, auth, media pipeline, feed and MCP server already exist and are not repeated here.

Legend: `[ ]` not started, `[~]` in progress, `[x]` done. Priority: **P1** next, **P2** after that, **P3** later.

---

## 0. Already in the project (skip)

Inferred from `CLAUDE.md`. Check against `docs/STATUS.md` and move anything missing into the lists below.

| Area | What exists |
|---|---|
| Auth | Signup, login, logout, cookies + CSRF, Google sign in, Turnstile |
| Posts | Photo and video upload, AVIF/WebP variants, HLS video, text overlay |
| Feed | Fan-out on write to Redis, celebrity merge on read, buffered counters |
| Social | Likes, notifications (events dispatcher) |
| Business | Public business page `/business/[slug]` |
| Admin | Admin panel, `user` / `admin` / `superadmin` roles, test data batches |
| AI | Claude client, image moderation |
| MCP | MCP server at `/mcp` |

---

## 1. Social basics still missing (P1)

Build these first if `docs/STATUS.md` shows them missing.

- [x] Comments with threaded replies (one level)
- [x] Follow requests for private accounts
- [x] Search users and hashtags (`pg_trgm`)
- [x] Hashtag pages (top and recent)
- [x] Save / bookmark posts
- [x] Collections for saved posts
- [x] Tag and mention users in posts and comments
- [x] Block, mute and restrict
- [x] Hidden words filter for comments
- [x] Password reset and email verification
- [x] Share post (copy link, WhatsApp, native share)

## 2. Stories (P1)

- [x] Stories that disappear after 24 hours
- [x] Story viewers list and reactions
- [x] Story highlights on profile
- [x] Polls and quizzes in stories
- [x] Close friends list (story audience)
- [x] Festival story frames (Diwali, Holi, Eid, Christmas)

## 3. Creating and publishing (P1)

- [x] Save drafts
- [x] Schedule posts (published by beat)
- [x] Photo editing and filters (client side)
- [x] Collab posts (two authors on one post)
- [x] Pinned posts on profile (up to 3)
- [x] Time capsule posts (unlock on a future date)

## 4. Messaging (P1)

- [x] 1:1 direct messages over the existing `ws` process
- [x] Read receipts and typing indicator
- [x] Message requests from non-followers
- [x] Share posts into DMs
- [x] Group chats
- [x] Voice notes
- [x] Communities (group with posts and members)
- [~] Live translation in chat (tap to translate works, needs `ANTHROPIC_API_KEY` to run, not automatic)

## 5. Reels and live (P2)

- [x] Reels vertical feed (reuses HLS pipeline)
- [ ] Remix / duet on reels
- [~] Live streaming (managed provider) (LiveKit room, viewers join directly, no large-audience egress)
- [ ] Voice posts and audio rooms

## 6. Business features (P2)

Extends the existing business page.

- [ ] Services list with rates, phone, location, business hours
- [ ] "Book Now" and "Contact" buttons
- [ ] Booking with date and time slots
- [ ] Quotation requests
- [ ] Reviews and ratings, with owner replies
- [ ] Local search, "welder near me" (PostGIS)
- [ ] Booking reminders on WhatsApp / SMS
- [ ] Service portfolio (before / after photos)
- [ ] Business inbox with quick replies
- [ ] GST invoice for bookings

## 7. Plans, payments and promotion (P2)

### Plans
| Plan | Includes |
|---|---|
| Free | Basic features |
| Premium | No ads, verified badge, advanced editing |
| Creator | Tips, subscriptions, advanced analytics |
| Business | Booking button, analytics, many service listings |
| Enterprise | Many staff accounts, dedicated support |

### Features
- [ ] Subscriptions with Razorpay (UPI, cards)
- [ ] Verified badge
- [ ] Tips for creators
- [ ] Subscriber-only posts and stories
- [ ] Creator payouts (Razorpay Route)
- [ ] Boosted post
- [ ] Sponsored feed ad
- [ ] Story ad
- [ ] Local promotion (city or area)
- [ ] Featured listing in search
- [ ] Promotion budget, daily cap and report
- [ ] Analytics dashboard for users and businesses

## 8. AI features (P2)

Uses the existing `app/ai/llm_client.py` and the `ai` Celery queue.

Full plan: `docs/RedStarVibe_AI_RAG_MCP_Feature_Plan.docx`. Models run on Cloudflare Workers AI or Claude, as `AI_PROVIDER` says.

- [~] Semantic search with pgvector (written, needs Cloudflare keys, keyword search works without them)
- [~] Smart captions and hashtags from the photo (written, needs a provider key to run)
- [~] Similar posts (written, needs Cloudflare keys)
- [ ] Auto tags and summary for posts
- [~] Alt text for images (written with captions, needs a provider key to run)
- [x] Toxic comment warning before posting (word rules work, the model check needs a key)
- [x] For You tab from interests and likes (semantic matching needs Cloudflare keys)
- [x] Best time to post (plain statistics, no model)
- [~] Image moderation on Cloudflare (written, never run on the real model)
- [ ] Auto translation of comments
- [ ] Fact-check labels
- [~] Help chatbot (Vibe AI quotes sources, generated answers need `ANTHROPIC_API_KEY`)
- [~] Spam and fake account detection (sign up and follow burst signals reach the staff queue, no automatic action)
- [ ] Interest matching

## 9. New MCP tools (P2)

Add to the existing MCP server. Same role checks as the API.

| Tool | Who | Example |
|---|---|---|
| `search_posts` (done) | User, Admin | "Find my posts about Goa" |
| `get_profile` (done) | User, Admin | "How many followers do I have?" |
| `read_comments` (done) | User, Admin | "Summarize comments on my last post" |
| `get_my_analytics` (done) | User | "Which was my most popular post last month?" |
| `get_best_times`, `list_drafts`, `search_saved`, `ask_vibe_ai`, `suggest_caption`, `update_draft` (done) | User | "When should I post this week?" |
| `list_reported_posts` | Admin, Staff | "Which posts were reported today?" |
| `get_bookings` | Business | "What bookings do I have this week?" |

## 10. Roles and permissions (P1)

Extends the current `user` / `admin` / `superadmin` roles.

- [x] Add `staff` and `business` roles
- [x] Permission map (role to permissions) in one place
- [x] `require_permission("...")` dependency next to `AdminUser`
- [x] Support tickets (staff resolve, escalate to admin)
- [~] Ad approval queue (admin) (queue and business requests work, approved ads do not run because ad delivery is P2)
- [x] User and business verification (admin)
- [~] Plans, prices and revenue pages (superadmin) (plans and prices work, revenue is empty until payments, which are P2)
- [x] Audit log for every admin and staff action
- [~] Business staff accounts (Enterprise) (staff list only, no extra access and no plan check until bookings and payments)

| Permission | Superadmin | Admin | Staff | Business | User |
|---|:-:|:-:|:-:|:-:|:-:|
| Manage admins, plans, prices, revenue, settings | Yes | | | | |
| Verify users and businesses | Yes | Yes | | | |
| Remove reported posts, approve ads | Yes | Yes | | | |
| Resolve tickets, first-level moderation | Yes | Yes | Yes | | |
| Escalate to admin | | | Yes | | |
| Manage services and bookings | | | | Yes | |

## 11. Connect people (P3)

- [ ] Local discovery map
- [ ] Skill exchange
- [ ] Neighbourhood groups
- [ ] Mentorship matching
- [ ] Event planner with RSVP
- [ ] Challenges and streaks
- [ ] Memories (on this day)
- [ ] Digital wellbeing (time limits, break reminders)

## 12. Growth and account security (P2)

- [x] Choose interests (a card on the feed and Explore for new accounts)
- [ ] Phone OTP login
- [ ] Referral system with rewards
- [ ] Invite links and QR codes
- [ ] Contact sync (hashed, opt-in)
- [ ] Smart push notifications and preferences
- [x] Two-factor authentication
- [ ] Login activity and log out other devices
- [x] Data download and account delete
- [ ] Hindi and Indian languages
- [ ] Data saver mode
- [~] PWA and offline reading (installable with an offline page, no offline reading of posts)
- [ ] Teen accounts (private by default, limited DMs)

---

_See `plan.pdf` for how each feature fits the existing modules, events, workers and web routes._
