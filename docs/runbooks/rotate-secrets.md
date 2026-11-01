# Rotating secrets

| Secret | Effect of rotation |
|---|---|
| `JWT_SECRET` | All access and MCP tokens stop working. Refresh tokens are opaque, so web users get a new session silently. |
| `FIELD_ENCRYPTION_KEY` | Decrypt and re-encrypt `users.phone_encrypted` and `users.totp_secret_encrypted` first, or those values are lost. |
| `POSTGRES_PASSWORD` | Change it in Postgres, update `.env`, restart `pgbouncer` and the app services. |
| S3 keys, LiveKit, SMTP, Anthropic | Create new, update `.env`, restart app services, revoke old. |
