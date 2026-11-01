# Incident checklist

1. Check `/readyz`, `docker compose ps`, Grafana RED dashboard and Sentry.
2. Stuck media or posts: check `worker` logs and queue length, `redis-cli llen media`.
3. Feed wrong: delete `feed:<user id>`. It rebuilds from Postgres on next read.
4. Counters behind: check that `beat` is running. Likes stay in Redis until flushed.
5. Roll back by redeploying the previous image tag. Migrations are expand then contract, so old code keeps working.
