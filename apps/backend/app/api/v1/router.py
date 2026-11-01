from fastapi import APIRouter

from app.mcp.auth import router as oauth_router
from app.modules.admin.router import router as admin
from app.modules.assistant.router import router as assistant
from app.modules.auth.router import router as auth
from app.modules.calls.router import router as calls
from app.modules.chat.router import router as chat
from app.modules.comments.router import router as comments
from app.modules.feed.router import router as feed
from app.modules.follows.router import router as follows
from app.modules.media.router import router as media
from app.modules.moderation.router import router as moderation
from app.modules.notifications.router import router as notifications
from app.modules.posts.router import router as posts
from app.modules.reels.router import router as reels
from app.modules.search.router import router as search
from app.modules.stories.router import router as stories
from app.modules.users.router import router as users

api_router = APIRouter(prefix="/api/v1")
for r in (
    auth, follows, users, media, posts, comments, feed, reels, stories, chat, calls, notifications,
    search, moderation, admin, assistant, oauth_router,
):
    api_router.include_router(r)
