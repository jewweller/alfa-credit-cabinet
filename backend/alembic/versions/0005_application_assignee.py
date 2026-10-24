"""Исполнитель заявки в банке.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("assignee_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_applications_assignee_id_users", "users", ["assignee_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.drop_constraint("fk_applications_assignee_id_users", type_="foreignkey")
        batch.drop_column("assignee_id")
