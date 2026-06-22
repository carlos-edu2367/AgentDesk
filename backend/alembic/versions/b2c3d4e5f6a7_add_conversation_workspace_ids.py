"""add conversations.workspace_ids

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-21 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(sa.Column("workspace_ids", sa.JSON(), nullable=True))
    # Backfill existing rows so they serialize as an empty grant, not NULL.
    op.execute("UPDATE conversations SET workspace_ids = '[]' WHERE workspace_ids IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("workspace_ids")
