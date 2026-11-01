COMPOSE = docker compose --env-file .env -f infra/docker/docker-compose.yml

.PHONY: up down logs seed test test-web e2e lint types load

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

seed:
	$(COMPOSE) exec -T api python -m scripts.seed

test:
	docker build -q -t rsv-test --target test apps/backend
	$(COMPOSE) up -d db pgbouncer redis objectstore storage-init migrate
	. ./.env; docker run --rm --network redstarvibe_internal -e APP_ENV=test -e BREACHED_PASSWORD_CHECK=false \
	  -e DATABASE_URL=postgresql+asyncpg://rsv:$$POSTGRES_PASSWORD@pgbouncer:5432/redstarvibe -e REDIS_URL=redis://redis:6379/0 \
	  -e JWT_SECRET=testsecrettestsecrettestsecrettestsecret rsv-test python -m pytest -q --cov=app/modules

test-web:
	cd apps/web && npm run test && npm run typecheck && npm run lint

e2e:
	cd apps/web && npx playwright test

lint:
	docker build -q -t rsv-test --target test apps/backend
	docker run --rm rsv-test sh -c "ruff check app tests && mypy app"

types:
	docker run --rm -e APP_ENV=local redstarvibe/backend:local python -c "import json;from app.main import app;print(json.dumps(app.openapi()))" > packages/api-types/openapi.json
	cd apps/web && npm run gen:api

load:
	docker run --rm --network redstarvibe_internal -e BASE_URL=http://api:8000 -v "$(CURDIR)/apps/backend/tests/load:/k6" grafana/k6 run /k6/feed.js
