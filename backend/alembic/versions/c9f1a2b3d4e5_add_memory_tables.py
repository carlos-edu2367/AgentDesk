"""add memory tables

Revision ID: c9f1a2b3d4e5
Revises: 8f3a2d1b4c9e
Create Date: 2026-06-18 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c9f1a2b3d4e5'
down_revision: Union[str, None] = '8f3a2d1b4c9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('memories', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column('memories', sa.Column('embedding_status', sa.String(), nullable=True, server_default='pending'))

    op.create_table('memory_embeddings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('memory_id', sa.String(), nullable=True),
        sa.Column('embedding_model', sa.String(), nullable=True),
        sa.Column('embedding_vector', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['memory_id'], ['memories.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('memory_links',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('source_memory_id', sa.String(), nullable=True),
        sa.Column('target_memory_id', sa.String(), nullable=True),
        sa.Column('relation_type', sa.String(), nullable=True),
        sa.Column('strength', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['source_memory_id'], ['memories.id']),
        sa.ForeignKeyConstraint(['target_memory_id'], ['memories.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('memory_usage',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('memory_id', sa.String(), nullable=True),
        sa.Column('execution_id', sa.String(), nullable=True),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['executions.id']),
        sa.ForeignKeyConstraint(['memory_id'], ['memories.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('memory_usage')
    op.drop_table('memory_links')
    op.drop_table('memory_embeddings')
    op.drop_column('memories', 'embedding_status')
    op.drop_column('memories', 'deleted_at')
