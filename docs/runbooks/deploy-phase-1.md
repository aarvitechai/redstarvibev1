# Deploy Phase 1 (one server)

1. Create an arm64 or amd64 VM (the guide suggests Oracle Always Free). Install Docker. Allow only ports 22 (from your IP) and 443.
2. Point the `redstarvibe.com` nameservers to Cloudflare. Apply `infra/terraform/envs/production`, which creates DNS and R2 buckets.
3. Create R2 API keys. Add a custom domain `media.redstarvibe.com` to the public bucket. Allow `PUT` from your site in the raw bucket CORS rules.
4. Create a LiveKit Cloud project. Set up your SMTP provider. Get an Anthropic API key.
5. Clone the repo to `/srv/redstarvibe`, run `python3 scripts/bootstrap_env.py`, then edit `.env`:

   ```
   APP_ENV=production
   PUBLIC_URL=https://redstarvibe.com
   ALLOWED_ORIGINS=https://redstarvibe.com
   COOKIE_SECURE=true
   ADMIN_IP_ALLOWLIST=<your office IP>
   S3_ENDPOINT=https://<account>.r2.cloudflarestorage.com
   S3_PUBLIC_ENDPOINT=https://<account>.r2.cloudflarestorage.com
   MEDIA_PUBLIC_BASE=https://media.redstarvibe.com
   LIVEKIT_URL=wss://<project>.livekit.cloud
   LIVEKIT_API_KEY=...
   LIVEKIT_API_SECRET=...
   SMTP_HOST=... SMTP_USER=... SMTP_PASSWORD=... SMTP_TLS=true
   ANTHROPIC_API_KEY=...
   TURNSTILE_SECRET=... TURNSTILE_SITE_KEY=...
   SENTRY_DSN=...
   ```
6. Start: `IMAGE_TAG=<sha> docker compose --env-file .env -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.prod.yml up -d`
7. Put TLS in front with a Cloudflare Tunnel to `http://127.0.0.1:8080`, and enable Cloudflare WAF managed rules.
8. Never run `scripts.seed` in production. It refuses to run there.
9. Promote your first admin: `UPDATE users SET role='admin' WHERE username='...'`. In production, admins must enable MFA.
10. Schedule backups: see `restore-database.md`.
