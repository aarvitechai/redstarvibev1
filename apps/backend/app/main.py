"""App factory. The API and WebSocket gateway run from this code as separate deployments."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

from app import models  # noqa: F401
from app.api.v1.router import api_router
from app.core.cache import get_redis
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.errors import install_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.core.telemetry import setup_telemetry
from app.mcp.auth import metadata
from app.realtime.gateway import router as ws_router


@asynccontextmanager
async def lifespan(_: FastAPI):  # type: ignore[no-untyped-def]
    setup_logging()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="RedStarVibe API", version="1.0.0", lifespan=lifespan,
        docs_url=None if settings.is_prod else "/api/docs",
        redoc_url=None,
        openapi_url=None if settings.is_prod else "/api/openapi.json",
    )
    install_handlers(app)
    setup_telemetry(app)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(api_router)
    app.include_router(ws_router)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz() -> dict[str, str]:
        async with SessionLocal() as s:
            await s.execute(text("SELECT 1"))
        await get_redis().ping()
        return {"status": "ready"}

    @app.get("/.well-known/oauth-authorization-server", include_in_schema=False)
    async def oauth_metadata(request: Request) -> dict[str, object]:
        return metadata(request)

    return app


app = create_app()
