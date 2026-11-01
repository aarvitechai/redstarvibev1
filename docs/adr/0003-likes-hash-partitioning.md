# 0003: `likes` is hash partitioned, not time partitioned

Accepted. The guide (section 6.2) asks for time partitioning on `likes`, `messages` and `notifications`. Postgres requires the
partition key to be part of the primary key. `likes` needs the primary key `(user_id, post_id)` to enforce one like per user per
post, and adding `created_at` would break that. So `likes` uses 16 hash partitions on `user_id`. `messages` and `notifications`
use monthly range partitions as the guide says, created ahead of time by Celery Beat.
