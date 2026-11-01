"""Each prefork child keeps one event loop, so pooled DB and Redis connections stay valid between tasks."""
import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")
_loop: asyncio.AbstractEventLoop | None = None


def run(coro: Coroutine[Any, Any, T]) -> T:
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop.run_until_complete(coro)
