"""Результаты обработки заявки: обогащение, скоринг, решение, оффер, запрос документов.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DOCUMENT = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
_MONEY = sa.Numeric(14, 2)
_NOW = sa.DateTime(timezone=True)


def _application_fk() -> sa.Column:
    return sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "enrichment_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _application_fk(),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("response", _DOCUMENT, nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(255), nullable=True),
        sa.Column("fetched_at", _NOW, nullable=False),
    )
    op.create_table(
        "scoring_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _application_fk(),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False),
        sa.Column("grade", sa.String(1), nullable=False),
        sa.Column("factors", _DOCUMENT, nullable=False),
        sa.Column("created_at", _NOW, nullable=False),
    )
    op.create_table(
        "decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _application_fk(),
        sa.Column(
            "scoring_result_id", sa.Uuid(), sa.ForeignKey("scoring_results.id"), nullable=True
        ),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("client_reason", sa.String(32), nullable=True),
        sa.Column("rules_fired", _DOCUMENT, nullable=False),
        sa.Column("decided_by", sa.String(16), nullable=False),
        sa.Column("underwriter_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.Column("created_at", _NOW, nullable=False),
    )
    op.create_table(
        "offers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _application_fk(),
        sa.Column("decision_id", sa.Uuid(), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("amount", _MONEY, nullable=False),
        sa.Column("term_months", sa.Integer(), nullable=False),
        sa.Column("rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("monthly_payment", _MONEY, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", _NOW, nullable=False),
    )
    op.create_table(
        "info_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _application_fk(),
        sa.Column("decision_id", sa.Uuid(), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("items", _DOCUMENT, nullable=False),
        sa.Column("message", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", _NOW, nullable=False),
    )
    for table in ("enrichment_results", "scoring_results", "decisions", "offers", "info_requests"):
        op.create_index(f"ix_{table}_application_id", table, ["application_id"])


def downgrade() -> None:
    for table in ("info_requests", "offers", "decisions", "scoring_results", "enrichment_results"):
        op.drop_index(f"ix_{table}_application_id", table_name=table)
        op.drop_table(table)
