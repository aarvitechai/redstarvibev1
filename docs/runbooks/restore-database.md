# Backups and restore

Backup, daily and encrypted: `docker compose exec -T db pg_dump -U rsv -Fc redstarvibe | age -r <public key> > backup-$(date +%F).dump.age`,
then upload to a separate R2 bucket. Point in time recovery needs a managed Postgres or WAL archiving (Phase 2).

Restore: stop `api ws mcp worker beat`, then `age -d -i key.txt backup.dump.age | docker compose exec -T db pg_restore -U rsv -d redstarvibe --clean --if-exists`, then start them and check `/readyz`.

Test a restore monthly on a scratch machine.
