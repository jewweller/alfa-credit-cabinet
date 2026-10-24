"""Подпись договора и выдача.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signatures",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("offer_id", sa.Uuid(), sa.ForeignKey("offers.id"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_signatures_application_id", "signatures", ["application_id"])
    op.create_table(
        "disbursements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("applications.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("offer_id", sa.Uuid(), sa.ForeignKey("offers.id"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("account_mask", sa.String(16), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("disbursements")
    op.drop_index("ix_signatures_application_id", table_name="signatures")
    op.drop_table("signatures")
