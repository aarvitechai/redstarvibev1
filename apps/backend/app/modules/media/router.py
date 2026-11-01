import uuid

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, Db
from app.modules.media import service
from app.modules.media.schemas import AssetOut, UploadIn, UploadOut

router = APIRouter(prefix="/media", tags=["media"])


def _origin(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    return f"{request.headers.get('x-forwarded-proto', request.url.scheme)}://{host}"


@router.post("/uploads", response_model=UploadOut, status_code=201)
async def create_upload(data: UploadIn, request: Request, me: CurrentUser, s: Db) -> UploadOut:
    return await service.create_upload(s, me, data, _origin(request))


@router.post("/{asset_id}/complete", response_model=AssetOut)
async def complete(asset_id: uuid.UUID, me: CurrentUser, s: Db) -> AssetOut:
    return await service.complete(s, me, asset_id)


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(asset_id: uuid.UUID, me: CurrentUser, s: Db) -> AssetOut:
    return await service.get_owned(s, me, asset_id)
