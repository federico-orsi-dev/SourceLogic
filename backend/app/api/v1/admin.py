from __future__ import annotations

import hashlib
import secrets
from hmac import compare_digest

from app.core.config import settings
from app.core.database import get_db
from app.models import TenantAPIKey
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/admin", tags=["admin"])


class APIKeyResponse(BaseModel):
    id: int
    tenant_id: str
    label: str
    key: str | None = None  # only returned on creation


class APIKeyInfo(BaseModel):
    id: int
    tenant_id: str
    label: str
    is_active: bool


def _require_admin(
    x_admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),
) -> None:
    if not settings.ADMIN_SECRET:
        raise HTTPException(status_code=503, detail="Admin endpoints are not configured.")
    if not x_admin_secret or not compare_digest(x_admin_secret, settings.ADMIN_SECRET):
        raise HTTPException(status_code=401, detail="Invalid admin secret.")


@router.post(
    "/tenants/{tenant_id}/keys",
    response_model=APIKeyResponse,
    status_code=201,
    dependencies=[Depends(_require_admin)],
)
async def create_api_key(
    tenant_id: str,
    label: str = "default",
    db: AsyncSession = Depends(get_db),
) -> APIKeyResponse:
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    record = TenantAPIKey(tenant_id=tenant_id, key_hash=key_hash, label=label)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return APIKeyResponse(id=record.id, tenant_id=record.tenant_id, label=record.label, key=raw_key)


@router.get(
    "/tenants/{tenant_id}/keys",
    response_model=list[APIKeyInfo],
    dependencies=[Depends(_require_admin)],
)
async def list_api_keys(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[APIKeyInfo]:
    result = await db.execute(select(TenantAPIKey).where(TenantAPIKey.tenant_id == tenant_id))
    return [
        APIKeyInfo(id=r.id, tenant_id=r.tenant_id, label=r.label, is_active=r.is_active)
        for r in result.scalars().all()
    ]


@router.delete(
    "/tenants/{tenant_id}/keys/{key_id}",
    status_code=204,
    dependencies=[Depends(_require_admin)],
)
async def revoke_api_key(
    tenant_id: str,
    key_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    record = await db.get(TenantAPIKey, key_id)
    if not record or record.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="API key not found.")
    record.is_active = False
    await db.commit()
