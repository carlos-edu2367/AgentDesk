"""add plugin sdk tables

Revision ID: e5f6a7b8c9d0
Revises: d4e6f7a8b9c0
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("plugins", sa.Column("install_path", sa.String(), nullable=True))
    op.add_column("plugins", sa.Column("tools_json", sa.JSON(), nullable=True))
    op.add_column("plugins", sa.Column("skills_json", sa.JSON(), nullable=True))
    op.add_column("plugins", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("skills", sa.Column("plugin_id", sa.String(), nullable=True))
    op.create_table(
        "agent_plugins",
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("plugin_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"]),
        sa.PrimaryKeyConstraint("agent_id", "plugin_id"),
    )
    op.create_table(
        "team_plugins",
        sa.Column("team_id", sa.String(), nullable=False),
        sa.Column("plugin_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"]),
        sa.PrimaryKeyConstraint("team_id", "plugin_id"),
    )


def downgrade() -> None:
    op.drop_table("team_plugins")
    op.drop_table("agent_plugins")
    op.drop_column("skills", "plugin_id")
    op.drop_column("plugins", "deleted_at")
    op.drop_column("plugins", "skills_json")
    op.drop_column("plugins", "tools_json")
    op.drop_column("plugins", "install_path")
