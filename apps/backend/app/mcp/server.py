"""MCP server (official Python SDK) over Streamable HTTP. Run: uvicorn app.mcp.server:app --port 8001"""
import functools
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar

import jwt
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import AnyHttpUrl

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import setup_logging
from app.core.security import decode_token
from app.mcp.tools import handlers

setup_logging()
P = ParamSpec("P")
R = TypeVar("R")
BASE = settings.mcp_issuer or settings.public_url or "http://localhost:8080"


class JwtVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            payload = decode_token(token, typ="mcp")
        except jwt.InvalidTokenError:
            return None
        return AccessToken(
            token=token, client_id=str(payload.get("client_id")), scopes=str(payload.get("scope", "")).split(),
            expires_at=int(payload["exp"]),  # type: ignore[call-overload]
            subject=str(payload["sub"]),
        )


mcp = MCPServer(
    "RedStarVibe",
    instructions="Tools for working with the signed in user's RedStarVibe account. Writes create drafts only.",
    token_verifier=JwtVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(BASE), resource_server_url=AnyHttpUrl(f"{BASE}/mcp"), required_scopes=["read"],
        validate_token_resource=False,  # JwtVerifier already checks the mcp audience
    ),
)


def _uid(scope: str | None = None) -> uuid.UUID:
    token = get_access_token()
    if token is None or token.subject is None:
        raise ToolError("Not authenticated")
    if scope and scope not in token.scopes:
        raise ToolError(f"This token does not have the {scope} scope")
    return uuid.UUID(token.subject)


def _safe(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Business errors reach the agent with their message. Anything unexpected stays generic."""

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await fn(*args, **kwargs)
        except (AppError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


@mcp.tool()
@_safe
async def search_posts(query: str, limit: int = 10) -> dict[str, Any]:
    """Search public posts and the user's own content."""
    return await handlers.search_posts(_uid("read"), query, limit)


@mcp.tool()
@_safe
async def get_profile(username: str | None = None) -> dict[str, Any]:
    """Get a profile and stats. Omit username for the signed in user."""
    return await handlers.get_profile(_uid("read"), username)


@mcp.tool()
@_safe
async def get_post_insights(post_id: str) -> dict[str, Any]:
    """Reach, likes and comments for one of the user's own posts."""
    return await handlers.get_post_insights(_uid("read"), post_id)


@mcp.tool()
@_safe
async def draft_post(asset_ids: list[str], caption: str = "", location: str | None = None) -> dict[str, Any]:
    """Create a draft from already uploaded media. Drafts are never published automatically."""
    return await handlers.draft_post(_uid("write:drafts"), asset_ids, caption, location)


@mcp.tool()
@_safe
async def schedule_post(post_id: str, publish_at: str, user_confirmed: bool = False) -> dict[str, Any]:
    """Schedule a draft (ISO 8601 time with timezone). Requires the user's explicit confirmation."""
    return await handlers.schedule_post(_uid("write:drafts"), post_id, publish_at, user_confirmed)


@mcp.tool()
@_safe
async def list_notifications(limit: int = 20) -> dict[str, Any]:
    """Recent activity for the signed in user."""
    return await handlers.list_notifications(_uid("read"), limit)


@mcp.tool()
@_safe
async def report_content(entity_type: str, entity_id: str, reason: str, details: str | None = None) -> dict[str, Any]:
    """File a moderation report. entity_type: post, comment, user, story, message."""
    return await handlers.report_content(_uid("write:drafts"), entity_type, entity_id, reason, details)


# Host 0.0.0.0: inside the container, reachable only through nginx, which sets the public Host header.
app = mcp.streamable_http_app(stateless_http=True, streamable_http_path="/mcp", host="0.0.0.0")  # noqa: S104
