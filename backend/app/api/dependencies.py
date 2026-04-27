from __future__ import annotations

import hashlib

from app.core.config import settings
from app.core.database import get_db
from app.models import TenantAPIKey
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from jose import JWTError, jwt
except ImportError:
    JWTError = None  # noqa: F811
    jwt = None  # noqa: F811


async def get_current_tenant(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_tenant_id: str = Header(default="tenant-a", alias="X-Tenant-ID"),
    db: AsyncSession = Depends(get_db),
) -> str:
    """Authentication dispatcher: JWT → API key → dev mode."""
    if settings.AUTH_MODE == "jwt":
        if not jwt or not JWTError:
            raise HTTPException(
                status_code=503,
                detail="JWT support not installed. Install: uv add 'python-jose[cryptography]'",
            )
        if not settings.JWT_SECRET:
            raise HTTPException(
                status_code=503,
                detail="JWT_SECRET not configured in .env",
            )
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Bearer token required.")
        token = authorization.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
            tenant_id: str = payload.get("tenant_id", "")
            if not tenant_id:
                raise HTTPException(status_code=401, detail="Invalid token payload.")
            return tenant_id
        except JWTError as exc:
            raise HTTPException(status_code=401, detail="Invalid token.") from exc

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
