"""computer_use_conversation_flags

Revision ID: d55191bfff6b
Revises: d7e8f9a0b1c2
Create Date: 2026-06-22 22:50:03.484557

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd55191bfff6b'
down_revision: Union[str, None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("computer_use_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("conversations", sa.Column("computer_use_display", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("conversations", "computer_use_display")
    op.drop_column("conversations", "computer_use_enabled")
