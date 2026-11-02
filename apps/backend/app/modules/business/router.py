import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import CurrentUser, Db, require_permission
from app.core.rate_limit import client_ip
from app.modules.business import service
from app.modules.business.service import (
    AdIn,
    AdOut,
    PlanOut,
    PlanUpdate,
    ReviewIn,
    ReviewStatus,
    StaffIn,
    VerificationIn,
    VerificationOut,
)
from app.modules.users.models import User
from app.modules.users.schemas import UserBrief

router = APIRouter(tags=["business"])

Verifier = Annotated[User, Depends(require_permission("verify_accounts"))]
AdReviewer = Annotated[User, Depends(require_permission("approve_ads"))]
PlanManager = Annotated[User, Depends(require_permission("manage_plans"))]
Business = Annotated[User, Depends(require_permission("manage_business"))]


@router.post("/verification", response_model=VerificationOut, status_code=201)
async def request_verification(data: VerificationIn, me: CurrentUser, s: Db) -> VerificationOut:
    return await service.request_verification(s, me, data)


@router.get("/verification", response_model=VerificationOut | None)
async def my_verification(me: CurrentUser, s: Db) -> VerificationOut | None:
    return await service.my_verification(s, me)


@router.get("/admin/verification", response_model=list[VerificationOut])
async def verification_queue(_: Verifier, s: Db, status: ReviewStatus = "pending") -> list[VerificationOut]:
    return await service.verification_queue(s, status)


@router.post("/admin/verification/{request_id}/review", response_model=VerificationOut)
async def review_verification(request_id: uuid.UUID, data: ReviewIn, admin: Verifier, request: Request, s: Db) -> VerificationOut:
    return await service.review_verification(s, admin, request_id, data, client_ip(request))


@router.delete("/admin/verified/{username}", status_code=204)
async def remove_verified(username: str, admin: Verifier, request: Request, s: Db) -> None:
    await service.remove_verified(s, admin, username, client_ip(request))


@router.get("/plans", response_model=list[PlanOut])
async def public_plans(s: Db) -> list[PlanOut]:
    return await service.plans(s, only_active=True)


@router.get("/admin/plans", response_model=list[PlanOut])
async def all_plans(_: PlanManager, s: Db) -> list[PlanOut]:
    return await service.plans(s, only_active=False)


@router.put("/admin/plans/{code}", response_model=PlanOut)
async def update_plan(code: str, data: PlanUpdate, admin: PlanManager, request: Request, s: Db) -> PlanOut:
    return await service.update_plan(s, admin, code, data, client_ip(request))


@router.post("/business/ads", response_model=AdOut, status_code=201)
async def request_ad(data: AdIn, business: Business, s: Db) -> AdOut:
    return await service.request_ad(s, business, data)


@router.get("/business/ads", response_model=list[AdOut])
async def my_ads(business: Business, s: Db) -> list[AdOut]:
    return await service.my_ads(s, business)


@router.get("/admin/ads", response_model=list[AdOut])
async def ad_queue(_: AdReviewer, s: Db, status: ReviewStatus = "pending") -> list[AdOut]:
    return await service.ad_queue(s, status)


@router.post("/admin/ads/{ad_id}/review", response_model=AdOut)
async def review_ad(ad_id: uuid.UUID, data: ReviewIn, admin: AdReviewer, request: Request, s: Db) -> AdOut:
    return await service.review_ad(s, admin, ad_id, data, client_ip(request))


@router.get("/business/staff", response_model=list[UserBrief])
async def staff_list(business: Business, s: Db) -> list[UserBrief]:
    return await service.staff_list(s, business)


@router.post("/business/staff", status_code=204)
async def add_staff(data: StaffIn, business: Business, s: Db) -> None:
    await service.add_staff(s, business, data.username)


@router.delete("/business/staff/{user_id}", status_code=204)
async def remove_staff(user_id: uuid.UUID, business: Business, s: Db) -> None:
    await service.remove_staff(s, business, user_id)
