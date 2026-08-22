"""add investigation planning fields

Revision ID: b21d7abf3c4e
Revises: 7f0f4bb6b2d1
Create Date: 2026-08-22
"""

from alembic import op
import sqlalchemy as sa


revision = "b21d7abf3c4e"
down_revision = "7f0f4bb6b2d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("investigations", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column("investigations", sa.Column("domain", sa.String(length=64), nullable=True))
    op.add_column("investigations", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("investigations", sa.Column("error_message", sa.Text(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE investigations SET title = left(question, 255), domain = 'biotechnology' "
            "WHERE title IS NULL OR domain IS NULL"
        )
    )
    op.alter_column("investigations", "title", nullable=False, server_default="Scientific investigation")
    op.alter_column("investigations", "domain", nullable=False, server_default="biotechnology")


def downgrade() -> None:
    op.drop_column("investigations", "error_message")
    op.drop_column("investigations", "started_at")
    op.drop_column("investigations", "domain")
    op.drop_column("investigations", "title")
