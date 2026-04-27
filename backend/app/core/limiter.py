from __future__ import annotations

import hashlib

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _rate_limit_key(request: Request) -> str:
    """Rate-limit per API key (api_key mode) or per tenant ID (dev mode).

    Using the API key (hashed) as the bucket key prevents a single key from
    saturating the shared IP-based limit when many clients sit behind a NAT.
    Falls back to IP when neither header is present.
    """
    api_key = request.headers.get("X-API-Key")
    if api_key:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        return f"apikey:{key_hash}"
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        return f"tenant:{tenant_id}"
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)
