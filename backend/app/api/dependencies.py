from __future__ import annotations

import hashlib

from app.core.config import settings
from app.core.database import get_db
from app.models import TenantAPIKey
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_current_tenant(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_tenant_id: str = Header(default="tenant-a", alias="X-Tenant-ID"),
    db: AsyncSession = Depends(get_db),
) -> str:
    if settings.AUTH_MODE == "api_key":
        if not x_api_key:
            raise HTTPException(status_code=401, detail="X-API-Key header required.")
        key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
        result = await db.execute(
            select(TenantAPIKey)
            .where(TenantAPIKey.key_hash == key_hash)
            .where(TenantAPIKey.is_active == True)  # noqa: E712
        )
        record = result.scalar_one_or_none()
        if not record:
            raise HTTPException(status_code=401, detail="Invalid or expired API key.")
        return str(record.tenant_id)

    # dev mode: trust X-Tenant-ID header (safe for local single-user use)
    return x_tenant_id
