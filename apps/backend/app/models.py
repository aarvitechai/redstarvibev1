"""Imports every model so SQLAlchemy and Alembic see the whole schema."""
from app.ai.models import Embedding  # noqa: F401
from app.modules.auth.models import OAuthClient, RefreshToken  # noqa: F401
from app.modules.calls.models import Call, CallMember  # noqa: F401
from app.modules.chat.models import Conversation, ConversationMember, Message  # noqa: F401
from app.modules.comments.models import Comment  # noqa: F401
from app.modules.follows.models import Follow  # noqa: F401
from app.modules.media.models import BlockedHash, MediaAsset  # noqa: F401
from app.modules.moderation.models import AiOutputLog, Report  # noqa: F401
from app.modules.notifications.models import Notification, PushSubscription  # noqa: F401
from app.modules.posts.models import Collection, Hashtag, Like, Post, PostHashtag, PostMedia, Save  # noqa: F401
from app.modules.stories.models import Highlight, HighlightStory, Story, StoryView  # noqa: F401
from app.modules.users.models import AuditLog, Block, Profile, User  # noqa: F401
