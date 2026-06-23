"""add_execution_events_index

Revision ID: f7a8b9c0d1e2
Revises: d55191bfff6b
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, None] = 'd55191bfff6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_execution_events_exec_created',
        'execution_events',
        ['execution_id', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_execution_events_exec_created', table_name='execution_events')
