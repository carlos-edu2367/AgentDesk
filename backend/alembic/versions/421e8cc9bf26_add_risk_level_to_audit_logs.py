"""Add risk_level to audit_logs

Revision ID: 421e8cc9bf26
Revises: 3b268bba23ff
Create Date: 2026-06-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '421e8cc9bf26'
down_revision: Union[str, None] = '3b268bba23ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('audit_logs', sa.Column('risk_level', sa.String(), nullable=True, server_default='low'))


def downgrade() -> None:
    op.drop_column('audit_logs', 'risk_level')
