"""Only a super admin can change roles. Super admins themselves are created from the server command line."""
import uuid
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import bad_request, forbidden, not_found
from app.modules.admin import repository as repo
from app.modules.users import repository as users
from app.modules.users.models import User


class UserAdminOut(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    role: str
    status: str
    is_test: bool


class RoleIn(BaseModel):
    role: Literal["user", "admin"]


def out(u: User) -> UserAdminOut:
    return UserAdminOut(
        id=u.id, username=u.username, email=u.email, role=u.role, status=u.status, is_test=u.test_batch_id is not None
    )


async def search(s: AsyncSession, q: str) -> list[UserAdminOut]:
    return [out(u) for u in await repo.find_users(s, q.strip())]


async def set_role(s: AsyncSession, actor: User, user_id: uuid.UUID, role: str, ip: str | None) -> UserAdminOut:
    target = await users.by_id(s, user_id)
    if target is None:
        raise not_found("User")
    if target.id == actor.id:
        raise bad_request("own_role", "You cannot change your own role")
    if target.role == "superadmin":
        raise forbidden("A super admin's role can only be changed from the server")
    if target.test_batch_id is not None:
        raise bad_request("test_account", "Test accounts cannot be given roles")
    previous, target.role = target.role, role
    await users.audit(s, actor.id, "admin.role_change", str(target.id), ip, {"from": previous, "to": role})
    await s.commit()
    return out(target)
