"""0003_pr7_asset_status_metadata

Revision ID: 0003_pr7_asset_status_metadata
Revises: 0002_pr6_personas_depicts_mature
Create Date: 2026-11-23 09:15:00

PR7 (ADR-005): Add `status` and `metadata` columns to `assets` for bounded retry
operator-review escalation (`status = "needs_review"`, `metadata["review_required"] = True`).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_pr7_asset_status_metadata"
down_revision: Union[str, None] = "0002_pr6_personas_depicts_mature"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assets",
        sa.Column("status", sa.Text(), nullable=False, server_default="ready"),
    )
    op.add_column(
        "assets",
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("assets", "metadata")
    op.drop_column("assets", "status")
