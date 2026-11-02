"""Verification, plans, ad review and business staff."""
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import bad_request, conflict, not_found
from app.core.permissions import STAFF_ROLES
from app.core.rate_limit import hit
from app.modules.business.models import AdRequest, BusinessStaff, Plan, VerificationRequest
from app.modules.notifications.service import notify
from app.modules.posts import repository as posts
from app.modules.users import repository as users
from app.modules.users import service as user_service
from app.modules.users.models import User
from app.modules.users.schemas import UserBrief

ReviewStatus = Literal["pending", "approved", "rejected"]


class VerificationIn(BaseModel):
    kind: Literal["person", "business"]
    details: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1000)]


class ReviewIn(BaseModel):
    approve: bool
    reason: str | None = Field(None, max_length=300)


class VerificationOut(BaseModel):
    id: uuid.UUID
    username: str
    kind: str
    details: str
    status: str
    reason: str | None
    created_at: datetime


class PlanOut(BaseModel):
    code: str
    name: str
    includes: str
    price_paise: int | None
    active: bool


class PlanUpdate(BaseModel):
    price_paise: int | None = Field(None, ge=0, le=100_000_000)
    active: bool
    includes: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class AdIn(BaseModel):
    post_id: uuid.UUID
    headline: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=80)]
    city: str | None = Field(None, max_length=80)
    daily_budget_paise: int = Field(ge=100, le=100_000_000)


class AdOut(BaseModel):
    id: uuid.UUID
    business: str
    post_id: uuid.UUID
    headline: str
    city: str | None
    daily_budget_paise: int
    status: str
    reason: str | None
    created_at: datetime


class StaffIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)


def _verification_out(r: VerificationRequest) -> VerificationOut:
    return VerificationOut(
        id=r.id, username=r.user.username, kind=r.kind, details=r.details, status=r.status, reason=r.reason,
        created_at=r.created_at,
    )


async def request_verification(s: AsyncSession, user: User, data: VerificationIn) -> VerificationOut:
    await hit(f"verify_request:user:{user.id}", 5, 86400)
    if user.verified:
        raise conflict("already_verified", "This account is already verified")
    request = VerificationRequest(user_id=user.id, kind=data.kind, details=data.details)
    request.user = user
    s.add(request)
    try:
        await s.commit()
    except IntegrityError as exc:
        await s.rollback()
        raise conflict("already_pending", "Your earlier request is still being reviewed") from exc
    return _verification_out(request)


async def my_verification(s: AsyncSession, user: User) -> VerificationOut | None:
    q = select(VerificationRequest).where(VerificationRequest.user_id == user.id).order_by(VerificationRequest.id.desc()).limit(1)
    row = (await s.execute(q)).scalars().first()
    return _verification_out(row) if row else None


async def verification_queue(s: AsyncSession, status: ReviewStatus) -> list[VerificationOut]:
    q = select(VerificationRequest).where(VerificationRequest.status == status).order_by(VerificationRequest.id).limit(100)
    return [_verification_out(r) for r in (await s.execute(q)).scalars().unique()]


async def review_verification(
    s: AsyncSession, admin: User, request_id: uuid.UUID, data: ReviewIn, ip: str | None
) -> VerificationOut:
    request = await s.get(VerificationRequest, request_id)
    if request is None:
        raise not_found("Request")
    if request.status != "pending":
        raise conflict("already_reviewed", "Someone already reviewed this request")
    request.status = "approved" if data.approve else "rejected"
    request.reason, request.reviewed_by, request.reviewed_at = data.reason, admin.id, datetime.now(UTC)
    if data.approve:
        request.user.verified = True
        # A business account gets business tools. Staff keep their role, so this can never lower it.
        if request.kind == "business" and request.user.role not in STAFF_ROLES:
            request.user.role = "business"
    await users.audit(s, admin.id, f"admin.verification.{request.status}", str(request.user_id), ip, {"kind": request.kind})
    await notify(s, request.user_id, f"verification_{request.status}", None, None)
    await s.commit()
    return _verification_out(request)


async def remove_verified(s: AsyncSession, admin: User, username: str, ip: str | None) -> None:
    user = await users.by_username(s, username)
    if user is None:
        raise not_found("User")
    user.verified = False
    await users.audit(s, admin.id, "admin.verification.removed", str(user.id), ip)
    await s.commit()


def _plan_out(p: Plan) -> PlanOut:
    return PlanOut(code=p.code, name=p.name, includes=p.includes, price_paise=p.price_paise, active=p.active)


async def plans(s: AsyncSession, only_active: bool) -> list[PlanOut]:
    q = select(Plan).order_by(Plan.position)
    q = q.where(Plan.active.is_(True)) if only_active else q
    return [_plan_out(p) for p in (await s.execute(q)).scalars()]


async def update_plan(s: AsyncSession, admin: User, code: str, data: PlanUpdate, ip: str | None) -> PlanOut:
    plan = await s.get(Plan, code)
    if plan is None:
        raise not_found("Plan")
    before = plan.price_paise
    plan.price_paise, plan.active, plan.includes = data.price_paise, data.active, data.includes
    change = {"price_from": before, "price_to": data.price_paise, "active": data.active}
    await users.audit(s, admin.id, "admin.plan.update", code, ip, change)
    await s.commit()
    return _plan_out(plan)


def _ad_out(a: AdRequest) -> AdOut:
    return AdOut(
        id=a.id, business=a.business.username, post_id=a.post_id, headline=a.headline, city=a.city,
        daily_budget_paise=a.daily_budget_paise, status=a.status, reason=a.reason, created_at=a.created_at,
    )


async def request_ad(s: AsyncSession, business: User, data: AdIn) -> AdOut:
    await hit(f"ad_request:user:{business.id}", 30, 86400)
    post = await posts.get(s, data.post_id)
    if post is None or post.author_id != business.id or post.status != "published":
        raise bad_request("invalid_post", "You can only promote your own published posts")
    ad = AdRequest(
        business_id=business.id, post_id=post.id, headline=data.headline, city=(data.city or "").strip() or None,
        daily_budget_paise=data.daily_budget_paise,
    )
    ad.business = business
    s.add(ad)
    await s.commit()
    return _ad_out(ad)


async def my_ads(s: AsyncSession, business: User) -> list[AdOut]:
    q = select(AdRequest).where(AdRequest.business_id == business.id).order_by(AdRequest.id.desc()).limit(100)
    return [_ad_out(a) for a in (await s.execute(q)).scalars().unique()]


async def ad_queue(s: AsyncSession, status: ReviewStatus) -> list[AdOut]:
    q = select(AdRequest).where(AdRequest.status == status).order_by(AdRequest.id).limit(100)
    return [_ad_out(a) for a in (await s.execute(q)).scalars().unique()]


async def review_ad(s: AsyncSession, admin: User, ad_id: uuid.UUID, data: ReviewIn, ip: str | None) -> AdOut:
    ad = await s.get(AdRequest, ad_id)
    if ad is None:
        raise not_found("Ad")
    if ad.status != "pending":
        raise conflict("already_reviewed", "Someone already reviewed this ad")
    ad.status = "approved" if data.approve else "rejected"
    ad.reason, ad.reviewed_by, ad.reviewed_at = data.reason, admin.id, datetime.now(UTC)
    await users.audit(s, admin.id, f"admin.ad.{ad.status}", str(ad.id), ip)
    await notify(s, ad.business_id, f"ad_{ad.status}", None, ad.post_id)
    await s.commit()
    return _ad_out(ad)


async def staff_list(s: AsyncSession, business: User) -> list[UserBrief]:
    q = select(User).join(BusinessStaff, BusinessStaff.user_id == User.id).where(BusinessStaff.business_id == business.id)
    return [user_service.brief(u) for u in (await s.execute(q.order_by(User.username))).scalars().unique()]


async def add_staff(s: AsyncSession, business: User, username: str) -> None:
    person = await users.by_username(s, username.strip().lstrip("@"))
    if (
        person is None or person.id == business.id or person.status != "active"
        or await users.is_blocked_either_way(s, business.id, person.id)
    ):
        raise bad_request("invalid_staff", "That person cannot be added")
    await s.execute(insert(BusinessStaff).values(business_id=business.id, user_id=person.id).on_conflict_do_nothing())
    await users.audit(s, business.id, "business.staff.add", str(person.id))
    await notify(s, person.id, "business_staff_added", business.id, None)
    await s.commit()


async def remove_staff(s: AsyncSession, business: User, user_id: uuid.UUID) -> None:
    await s.execute(delete(BusinessStaff).where(BusinessStaff.business_id == business.id, BusinessStaff.user_id == user_id))
    await users.audit(s, business.id, "business.staff.remove", str(user_id))
    await s.commit()
