# syntax=docker/dockerfile:1
FROM python:3.15-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
RUN pip install --no-cache-dir uv==0.5.29

FROM base AS deps
WORKDIR /srv
ARG UV_EXTRAS=""
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev $UV_EXTRAS

FROM base AS dev-deps
WORKDIR /srv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

FROM python:3.15-slim AS runtime-base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH=/opt/venv/bin:$PATH PYTHONPATH=/srv
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl \
  && rm -rf /var/lib/apt/lists/* \
  && useradd --create-home --uid 10001 app
WORKDIR /srv

FROM runtime-base AS test
COPY --from=dev-deps /opt/venv /opt/venv
COPY . .

FROM runtime-base AS production
COPY --from=deps /opt/venv /opt/venv
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts ./scripts
USER 10001
EXPOSE 8000
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--access-logfile", "-", "--timeout", "60", "--graceful-timeout", "30"]
