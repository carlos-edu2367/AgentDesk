"""add per-chat max_steps to conversations and executions

Revision ID: d7e8f9a0b1c2
Revises: c1d2e3f4a5b6
Create Date: 2026-06-22 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(sa.Column("max_steps", sa.Integer(), nullable=True))
    with op.batch_alter_table("executions") as batch:
        batch.add_column(sa.Column("max_steps", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("executions") as batch:
        batch.drop_column("max_steps")
    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("max_steps")
