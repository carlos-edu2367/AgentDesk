"""Add execution_approvals table

Revision ID: 8f3a2d1b4c9e
Revises: 421e8cc9bf26
Create Date: 2026-06-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8f3a2d1b4c9e'
down_revision: Union[str, None] = '421e8cc9bf26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'execution_approvals',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('execution_id', sa.String(), nullable=True),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('tool', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('risk_level', sa.String(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('arguments', sa.JSON(), nullable=True),
        sa.Column('pending_state', sa.JSON(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['executions.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('execution_approvals')
