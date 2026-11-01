#!/usr/bin/env python3
"""End to end check of the MCP server through the gateway: OAuth 2.1 + PKCE, then real tool calls.

Run inside the backend image, on the compose network:
  python verify_mcp.py http://gateway demo <password>
"""
import asyncio
import base64
import hashlib
import secrets
import sys
from urllib.parse import parse_qs, urlparse

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

BASE, USERNAME, PASSWORD = sys.argv[1], sys.argv[2], sys.argv[3]
REDIRECT = "http://localhost:9999/callback"


async def token_for(scope: str) -> str:
    async with httpx.AsyncClient(base_url=BASE, follow_redirects=False) as c:
        meta = (await c.get("/.well-known/oauth-authorization-server")).json()
        assert meta["code_challenge_methods_supported"] == ["S256"]
        client = (await c.post("/api/v1/oauth/register", json={"client_name": "verify", "redirect_uris": [REDIRECT]})).json()
        login = await c.post("/api/v1/auth/login", json={"identifier": USERNAME, "password": PASSWORD})
        assert login.status_code == 200, login.text
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        consent = await c.post(
            "/api/v1/oauth/consent",
            headers={"x-csrf-token": c.cookies.get("rsv_csrf")},
            json={"client_id": client["client_id"], "redirect_uri": REDIRECT, "code_challenge": challenge,
                  "state": "xyz", "scope": scope, "approve": True},
        )
        assert consent.status_code == 200, consent.text
        query = parse_qs(urlparse(consent.json()["redirect_to"]).query)
        assert query["state"] == ["xyz"]
        tok = await c.post("/api/v1/oauth/token", data={
            "grant_type": "authorization_code", "client_id": client["client_id"], "code": query["code"][0],
            "redirect_uri": REDIRECT, "code_verifier": verifier,
        })
        assert tok.status_code == 200, tok.text
        return tok.json()["access_token"]


async def main() -> None:
    async with httpx.AsyncClient() as raw:
        res = await raw.post(f"{BASE}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert res.status_code == 401, res.status_code
        print("unauthenticated request rejected: 401")

    token = await token_for("read")
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=httpx.Timeout(30, read=120)) as http:
        rest = await http.get(f"{BASE}/api/v1/auth/me")
        assert rest.status_code == 401, "an MCP token must not work on the REST API"
        print("MCP token rejected by the REST API: 401")
        async with streamable_http_client(f"{BASE}/mcp", http_client=http) as (read, write, *_):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = sorted(t.name for t in (await session.list_tools()).tools)
                print("tools:", tools)
                assert len(tools) == 7
                profile = await session.call_tool("get_profile", {})
                assert not profile.is_error and USERNAME in str(profile.content), profile
                print("get_profile ok")
                found = await session.call_tool("search_posts", {"query": "sunset"})
                assert not found.is_error and "sunset" in str(found.content).lower(), found
                print("search_posts ok")
                denied = await session.call_tool("draft_post", {"asset_ids": [], "caption": "x"})
                assert denied.is_error and "scope" in str(denied.content), denied
                print("draft_post refused without the write:drafts scope")
    print("MCP VERIFIED")


asyncio.run(main())
