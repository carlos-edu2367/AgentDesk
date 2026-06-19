"""add skill associations

Revision ID: d4e6f7a8b9c0
Revises: c9f1a2b3d4e5
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e6f7a8b9c0"
down_revision: Union[str, None] = "c9f1a2b3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("skills", sa.JSON(), nullable=True))
    op.add_column("skills", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("skills", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("skills", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    op.create_table(
        "agent_skills",
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("skill_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("agent_id", "skill_id"),
    )
    op.create_table(
        "team_skills",
        sa.Column("team_id", sa.String(), nullable=False),
        sa.Column("skill_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("team_id", "skill_id"),
    )


def downgrade() -> None:
    op.drop_table("team_skills")
    op.drop_table("agent_skills")
    op.drop_column("skills", "deleted_at")
    op.drop_column("skills", "updated_at")
    op.drop_column("skills", "created_at")
    op.drop_column("teams", "skills")
