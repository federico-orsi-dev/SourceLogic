"""scope root_path unique per tenant

Revision ID: a3f92b1cd045
Revises: 116ef13955e3
Create Date: 2026-04-16 12:00:00.000000

The uq_workspace_tenant_path constraint is already included in the initial
schema migration (116ef13955e3). This revision is kept as a no-op to preserve
the migration chain for databases that were created before the initial migration
was rewritten.
"""

from __future__ import annotations

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "a3f92b1cd045"
down_revision: Union[str, Sequence[str], None] = "116ef13955e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
