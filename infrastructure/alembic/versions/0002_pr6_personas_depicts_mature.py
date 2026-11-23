"""0002_pr6_personas_depicts_mature

Revision ID: 0002_pr6_personas_depicts_mature
Revises: 0001_baseline_v2
Create Date: 2026-11-23 08:40:00

PR6 (ADR-005): Add §41 persona versioning/soft-delete columns (`project_id`,
`parent_persona_id`, `avatar_asset_id`, `deleted_at`) and `mature` propagation
column on `asset_relationships`.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_pr6_personas_depicts_mature"
down_revision: Union[str, None] = "0001_baseline_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "personas",
        sa.Column("project_id", sa.UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=True),
    )
    op.add_column(
        "personas",
        sa.Column("parent_persona_id", sa.UUID(as_uuid=False), nullable=True),
    )
    op.add_column(
        "personas",
        sa.Column("avatar_asset_id", sa.UUID(as_uuid=False), sa.ForeignKey("assets.id"), nullable=True),
    )
    op.add_column(
        "personas",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "asset_relationships",
        sa.Column("mature", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("asset_relationships", "mature")
    op.drop_column("personas", "deleted_at")
    op.drop_column("personas", "avatar_asset_id")
    op.drop_column("personas", "parent_persona_id")
    op.drop_column("personas", "project_id")
