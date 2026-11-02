import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel

from app.api.deps import AdminUser, Db, SuperAdminUser, require_permission
from app.core.errors import forbidden
from app.core.pagination import Page, id_cursor
from app.core.permissions import has_permission
from app.core.rate_limit import client_ip, hit
from app.modules.admin import dashboard, reports, roles, service, test_data
from app.modules.admin import repository as repo
from app.modules.users import repository as users
from app.modules.users.models import User

router = APIRouter(prefix="/admin", tags=["admin"])

FirstLevel = Annotated[User, Depends(require_permission("moderate_first_level"))]
Escalator = Annotated[User, Depends(require_permission("escalate"))]
Period = Annotated[int, Query(ge=7, le=90)]
EntityType = Literal["post", "comment", "user", "story", "message", "community"]


class RemovedCount(BaseModel):
    batches: int


@router.get("/stats", response_model=service.Stats)
async def stats(_: AdminUser, s: Db) -> service.Stats:
    return await service.stats(s)


@router.get("/dashboard", response_model=dashboard.Dashboard)
async def admin_dashboard(_: AdminUser, s: Db, days: Period = 30) -> dashboard.Dashboard:
    return await dashboard.dashboard(s, days)


@router.get("/platform", response_model=dashboard.Platform)
async def platform(_: SuperAdminUser, s: Db, days: Period = 30) -> dashboard.Platform:
    return await dashboard.platform(s, days)


@router.get("/audit", response_model=Page[dashboard.AuditRow])
async def audit(
    _: SuperAdminUser, s: Db, category: Literal["admin", "staff", "business", "auth", "account", "mcp", "oauth"] | None = None,
    cursor: str | None = None, limit: int = Query(30, ge=1, le=100),
) -> Page[dashboard.AuditRow]:
    return await dashboard.audit_page(s, category, id_cursor(cursor), limit)


@router.get("/reports", response_model=Page[reports.AdminReport])
async def list_reports(
    _: FirstLevel, s: Db, status: reports.ReportStatus = "open", entity_type: EntityType | None = None,
    source: Literal["user", "ai"] | None = None, reason: str | None = Query(None, max_length=40),
    cursor: str | None = None, limit: int = Query(30, ge=1, le=100),
) -> Page[reports.AdminReport]:
    return await reports.page(s, status, entity_type, source, reason, id_cursor(cursor), limit)


@router.get("/reports/counts", response_model=reports.ReportCounts)
async def report_counts(_: FirstLevel, s: Db) -> reports.ReportCounts:
    return await reports.counts(s)


@router.get("/reports/export")
async def export_reports(
    admin: AdminUser, request: Request, s: Db, status: reports.ReportStatus = "all", entity_type: EntityType | None = None,
    source: Literal["user", "ai"] | None = None, reason: str | None = Query(None, max_length=40),
) -> Response:
    await hit(f"report_export:user:{admin.id}", 20, 3600)
    body = await reports.export_csv(s, status, entity_type, source, reason)
    await users.audit(s, admin.id, "admin.reports.export", status, client_ip(request))
    await s.commit()
    return Response(
        body, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="redstarvibe-reports.csv"'},
    )


@router.post("/reports/{report_id}/resolve", status_code=204)
async def resolve(report_id: uuid.UUID, data: service.ResolveIn, actor: FirstLevel, request: Request, s: Db) -> None:
    if data.action != "dismiss" and not has_permission(actor.role, "remove_reported"):
        raise forbidden("Staff can dismiss or escalate. An admin must remove content or suspend accounts.")
    await service.resolve(s, actor, report_id, data.action, client_ip(request))


@router.post("/reports/{report_id}/escalate", status_code=204)
async def escalate(report_id: uuid.UUID, actor: Escalator, request: Request, s: Db) -> None:
    await service.escalate(s, actor, report_id, client_ip(request))


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
