"""initial schema

Revision ID: 116ef13955e3
Revises:
Create Date: 2026-04-16 09:32:25.128276

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '116ef13955e3'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _create_fresh_schema() -> None:
    op.create_table(
        'workspaces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(length=50), server_default='tenant-a', nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('root_path', sa.String(length=1024), nullable=False),
        sa.Column(
            'status',
            sa.Enum('IDLE', 'INDEXING', 'FAILED', name='workspace_status', native_enum=False),
            nullable=False,
        ),
        sa.Column('last_indexed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'root_path', name='uq_workspace_tenant_path'),
    )
    op.create_index(op.f('ix_workspaces_id'), 'workspaces', ['id'], unique=False)
    op.create_index(op.f('ix_workspaces_tenant_id'), 'workspaces', ['tenant_id'], unique=False)

    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sessions_id'), 'sessions', ['id'], unique=False)
    op.create_index(op.f('ix_sessions_workspace_id'), 'sessions', ['workspace_id'], unique=False)

    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('sources', sa.JSON(), nullable=True),
        sa.Column('is_complete', sa.Boolean(), server_default='1', nullable=False),
        sa.Column(
            'timestamp',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_messages_id'), 'messages', ['id'], unique=False)
    op.create_index(op.f('ix_messages_session_id'), 'messages', ['session_id'], unique=False)
    op.create_index(op.f('ix_messages_timestamp'), 'messages', ['timestamp'], unique=False)


def _upgrade_legacy_sqlite_schema(inspector: sa.Inspector) -> None:
    bind = op.get_bind()
    workspace_columns = _column_names(inspector, 'workspaces')
    sessions_exists = _table_exists(inspector, 'sessions')
    messages_exists = _table_exists(inspector, 'messages')
    message_columns = _column_names(inspector, 'messages') if messages_exists else set()

    bind.exec_driver_sql("PRAGMA foreign_keys=OFF")

    bind.exec_driver_sql("DROP TABLE IF EXISTS _workspaces_new")
    bind.exec_driver_sql("DROP TABLE IF EXISTS _sessions_new")
    bind.exec_driver_sql("DROP TABLE IF EXISTS _messages_new")

    bind.exec_driver_sql(
        """
        CREATE TABLE _workspaces_new (
            id INTEGER NOT NULL,
            tenant_id VARCHAR(50) DEFAULT 'tenant-a' NOT NULL,
            name VARCHAR(200) NOT NULL,
            root_path VARCHAR(1024) NOT NULL,
            status VARCHAR(8) NOT NULL,
            last_indexed_at DATETIME,
            created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_workspace_tenant_path UNIQUE (tenant_id, root_path)
        )
        """
    )

    tenant_expr = "tenant_id" if "tenant_id" in workspace_columns else "'tenant-a'"
    bind.exec_driver_sql(
        f"""
        INSERT INTO _workspaces_new (
            id, tenant_id, name, root_path, status, last_indexed_at, created_at
        )
        SELECT
            id,
            {tenant_expr},
            name,
            root_path,
            status,
            last_indexed_at,
            created_at
        FROM workspaces
        """
    )

    if sessions_exists:
        bind.exec_driver_sql(
            """
            CREATE TABLE _sessions_new (
                id INTEGER NOT NULL,
                workspace_id INTEGER NOT NULL,
                title VARCHAR(200) NOT NULL,
                created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY(workspace_id) REFERENCES _workspaces_new (id) ON DELETE CASCADE
            )
            """
        )
        bind.exec_driver_sql(
            """
            INSERT INTO _sessions_new (id, workspace_id, title, created_at)
            SELECT id, workspace_id, title, created_at
            FROM sessions
            """
        )

    if messages_exists:
        bind.exec_driver_sql(
            """
            CREATE TABLE _messages_new (
                id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                sources JSON,
                is_complete BOOLEAN DEFAULT 1 NOT NULL,
                timestamp DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY(session_id) REFERENCES _sessions_new (id) ON DELETE CASCADE
            )
            """
        )
        is_complete_expr = "is_complete" if "is_complete" in message_columns else "1"
        bind.exec_driver_sql(
            f"""
            INSERT INTO _messages_new (
                id, session_id, role, content, sources, is_complete, timestamp
            )
            SELECT
                id,
                session_id,
                role,
                content,
                sources,
                {is_complete_expr},
                timestamp
            FROM messages
            """
        )

    if messages_exists:
        bind.exec_driver_sql("DROP TABLE messages")
    if sessions_exists:
        bind.exec_driver_sql("DROP TABLE sessions")
    bind.exec_driver_sql("DROP TABLE workspaces")

    bind.exec_driver_sql("ALTER TABLE _workspaces_new RENAME TO workspaces")
    if sessions_exists:
        bind.exec_driver_sql("ALTER TABLE _sessions_new RENAME TO sessions")
    if messages_exists:
        bind.exec_driver_sql("ALTER TABLE _messages_new RENAME TO messages")

    bind.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_workspaces_id ON workspaces (id)")
    bind.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_workspaces_tenant_id ON workspaces (tenant_id)")
    if sessions_exists:
        bind.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_sessions_id ON sessions (id)")
        bind.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_sessions_workspace_id ON sessions (workspace_id)"
        )
    else:
        op.create_table(
            'sessions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('workspace_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column(
                'created_at',
                sa.DateTime(timezone=True),
                server_default=sa.text('(CURRENT_TIMESTAMP)'),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_sessions_id'), 'sessions', ['id'], unique=False)
        op.create_index(op.f('ix_sessions_workspace_id'), 'sessions', ['workspace_id'], unique=False)
    if messages_exists:
        bind.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_messages_id ON messages (id)")
        bind.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_messages_session_id ON messages (session_id)"
        )
        bind.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_messages_timestamp ON messages (timestamp)")
    else:
        op.create_table(
            'messages',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('session_id', sa.Integer(), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('sources', sa.JSON(), nullable=True),
            sa.Column('is_complete', sa.Boolean(), server_default='1', nullable=False),
            sa.Column(
                'timestamp',
                sa.DateTime(timezone=True),
                server_default=sa.text('(CURRENT_TIMESTAMP)'),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_messages_id'), 'messages', ['id'], unique=False)
        op.create_index(op.f('ix_messages_session_id'), 'messages', ['session_id'], unique=False)
        op.create_index(op.f('ix_messages_timestamp'), 'messages', ['timestamp'], unique=False)

    bind.exec_driver_sql("PRAGMA foreign_keys=ON")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if _table_exists(inspector, 'workspaces'):
        _upgrade_legacy_sqlite_schema(inspector)
        return

    _create_fresh_schema()


def downgrade() -> None:
    op.drop_table('messages')
    op.drop_table('sessions')
    op.drop_table('workspaces')
