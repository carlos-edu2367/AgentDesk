"""add mcp stdio tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mcp_servers", sa.Column("tools_cache_json", sa.JSON(), nullable=True))
    op.add_column("mcp_servers", sa.Column("last_connected_at", sa.DateTime(), nullable=True))
    op.add_column("mcp_servers", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("mcp_servers", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_table(
        "agent_mcp_servers",
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("mcp_server_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["mcp_server_id"], ["mcp_servers.id"]),
        sa.PrimaryKeyConstraint("agent_id", "mcp_server_id"),
    )
    op.create_table(
        "team_mcp_servers",
        sa.Column("team_id", sa.String(), nullable=False),
        sa.Column("mcp_server_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["mcp_server_id"], ["mcp_servers.id"]),
        sa.PrimaryKeyConstraint("team_id", "mcp_server_id"),
    )


def downgrade() -> None:
    op.drop_table("team_mcp_servers")
    op.drop_table("agent_mcp_servers")
    op.drop_column("mcp_servers", "deleted_at")
    op.drop_column("mcp_servers", "last_error")
    op.drop_column("mcp_servers", "last_connected_at")
    op.drop_column("mcp_servers", "tools_cache_json")
