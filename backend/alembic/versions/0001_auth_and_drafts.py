"""Пользователи, компании, продукты, заявки и история статусов.

Revision ID: 0001
Revises:
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TAG_LIST = sa.ARRAY(sa.String(32)).with_variant(sa.JSON(), "sqlite")
_MONEY = sa.Numeric(14, 2)


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("inn", sa.String(12), nullable=False, unique=True),
        sa.Column("ogrn", sa.String(15), nullable=False),
        sa.Column("kind", sa.String(3), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("okved_main", sa.String(16), nullable=False),
        sa.Column("region", sa.String(128), nullable=False),
        sa.Column("registered_at", sa.Date(), nullable=False),
        sa.Column("segment", sa.String(8), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=True),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("purpose_tags", _TAG_LIST, nullable=False),
        sa.Column("min_amount", _MONEY, nullable=False),
        sa.Column("max_amount", _MONEY, nullable=False),
        sa.Column("min_term", sa.Integer(), nullable=False),
        sa.Column("max_term", sa.Integer(), nullable=False),
        sa.Column("base_rate", sa.Numeric(5, 2), nullable=False),
    )
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("number", sa.String(16), nullable=False, unique=True),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("applicant_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("amount", _MONEY, nullable=True),
        sa.Column("term_months", sa.Integer(), nullable=True),
        sa.Column("purpose", sa.String(32), nullable=True),
        sa.Column("revenue_12m", _MONEY, nullable=True),
        sa.Column("existing_payments_monthly", _MONEY, nullable=True),
        sa.Column("bki_consent", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_applications_company_id", "applications", ["company_id"])
    op.create_table(
        "application_status_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_application_status_history_application_id",
        "application_status_history",
        ["application_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_application_status_history_application_id")
    op.drop_table("application_status_history")
    op.drop_index("ix_applications_company_id")
    op.drop_table("applications")
    op.drop_table("products")
    op.drop_table("users")
    op.drop_table("companies")
