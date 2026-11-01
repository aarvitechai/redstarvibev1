import uuid

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from app.api.deps import AdminUser, Db, SuperAdminUser
from app.core.pagination import Page, id_cursor
from app.core.rate_limit import client_ip
from app.modules.admin import repository as repo
from app.modules.admin import roles, service, test_data
from app.modules.moderation.schemas import ReportOut

router = APIRouter(prefix="/admin", tags=["admin"])


class RemovedCount(BaseModel):
    batches: int


@router.get("/stats", response_model=service.Stats)
async def stats(_: AdminUser, s: Db) -> service.Stats:
    return await service.stats(s)


@router.get("/reports", response_model=Page[ReportOut])
async def reports(_: AdminUser, s: Db, cursor: str | None = None, limit: int = Query(30, le=100)) -> Page[ReportOut]:
    return await service.queue(s, id_cursor(cursor), limit)


@router.post("/reports/{report_id}/resolve", status_code=204)
async def resolve(report_id: uuid.UUID, data: service.ResolveIn, admin: AdminUser, request: Request, s: Db) -> None:
    await service.resolve(s, admin, report_id, data.action, client_ip(request))


@router.get("/test-data", response_model=list[test_data.BatchOut])
async def list_test_data(_: AdminUser, s: Db) -> list[test_data.BatchOut]:
    return [test_data.batch_out(b) for b in await repo.list_batches(s)]


@router.post("/test-data", response_model=test_data.BatchOut, status_code=202)
async def create_test_data(data: test_data.BatchIn, admin: AdminUser, request: Request, s: Db) -> test_data.BatchOut:
    return await test_data.request_create(s, admin, data, client_ip(request))


@router.delete("/test-data/{batch_id}", response_model=test_data.BatchOut, status_code=202)
async def remove_test_data(batch_id: uuid.UUID, admin: AdminUser, request: Request, s: Db) -> test_data.BatchOut:
    return await test_data.request_remove(s, admin, batch_id, client_ip(request))


@router.post("/test-data/remove-all", response_model=RemovedCount, status_code=202)
async def remove_all_test_data(admin: AdminUser, request: Request, s: Db) -> RemovedCount:
    return RemovedCount(batches=await test_data.request_remove_all(s, admin, client_ip(request)))


@router.get("/users", response_model=list[roles.UserAdminOut])
async def search_users(_: SuperAdminUser, s: Db, q: str = Query("", max_length=100)) -> list[roles.UserAdminOut]:
    return await roles.search(s, q)


@router.patch("/users/{user_id}/role", response_model=roles.UserAdminOut)
async def set_role(
    user_id: uuid.UUID, data: roles.RoleIn, actor: SuperAdminUser, request: Request, s: Db
) -> roles.UserAdminOut:
    return await roles.set_role(s, actor, user_id, data.role, client_ip(request))
