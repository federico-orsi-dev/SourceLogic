from fastapi import Header

def get_current_tenant(x_tenant_id: str = Header(default="tenant-a")) -> str:
    """
    Extracts the tenant ID from the X-Tenant-ID header.
    In a real SaaS, this would parse a JWT token and validate the organization context.
    For this portfolio project, it directly passes the isolated tenant scope.
    """
    return x_tenant_id
