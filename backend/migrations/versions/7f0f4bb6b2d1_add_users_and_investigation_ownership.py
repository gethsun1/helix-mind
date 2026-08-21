"""add users, roles, and investigation ownership

Revision ID: 7f0f4bb6b2d1
Revises: 4e4f8e4d6f60
Create Date: 2026-08-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "7f0f4bb6b2d1"
down_revision = "4e4f8e4d6f60"
branch_labels = None
depends_on = None

LEGACY_OWNER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("image", sa.Text(), nullable=True),
        sa.Column("role", sa.String(length=16), server_default="USER", nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=True),
        sa.Column("organization", sa.String(length=255), nullable=True),
        sa.Column("research_focus", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_account_id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.bulk_insert(
        sa.table(
            "users",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("email", sa.String()),
            sa.column("name", sa.String()),
            sa.column("role", sa.String()),
        ),
        [{"id": LEGACY_OWNER_ID, "email": "gethsun09@gmail.com", "name": "HelixMind Administrator", "role": "ADMIN"}],
    )

    op.add_column("investigations", sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_investigations_owner_id", "investigations", ["owner_id"], unique=False)
    op.execute(
        sa.text("UPDATE investigations SET owner_id = CAST(:owner_id AS UUID) WHERE owner_id IS NULL").bindparams(
            owner_id=LEGACY_OWNER_ID
        )
    )
    op.alter_column("investigations", "owner_id", nullable=False)
    op.create_foreign_key(
        "fk_investigations_owner_id_users",
        "investigations",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_investigations_owner_id_users", "investigations", type_="foreignkey")
    op.drop_index("ix_investigations_owner_id", table_name="investigations")
    op.drop_column("investigations", "owner_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
