"""Imports every model so SQLAlchemy and Alembic see the whole schema."""
from app.ai.models import Embedding  # noqa: F401
from app.modules.admin.models import TestDataBatch  # noqa: F401
from app.modules.auth.models import OAuthClient, RefreshToken  # noqa: F401
from app.modules.business.models import AdRequest, BusinessStaff, Plan, VerificationRequest  # noqa: F401
from app.modules.calls.models import Call, CallMember  # noqa: F401
from app.modules.chat.models import Conversation, ConversationMember, Message  # noqa: F401
from app.modules.comments.models import Comment  # noqa: F401
from app.modules.communities.models import Community, CommunityMember, CommunityPost  # noqa: F401
from app.modules.follows.models import Follow  # noqa: F401
from app.modules.media.models import BlockedHash, MediaAsset  # noqa: F401
from app.modules.moderation.models import AiOutputLog, Report  # noqa: F401
from app.modules.notifications.models import Notification, PushSubscription  # noqa: F401
from app.modules.posts.models import Collection, Hashtag, Like, Post, PostCollab, PostHashtag, PostMedia, PostTag, Save  # noqa: F401
from app.modules.stories.models import (  # noqa: F401
    CloseFriend,
    Highlight,
    HighlightStory,
    Story,
    StoryAnswer,
    StoryReaction,
    StoryView,
)
from app.modules.support.models import Ticket, TicketMessage  # noqa: F401
from app.modules.users.models import AuditLog, Block, Profile, User, UserLimit  # noqa: F401
