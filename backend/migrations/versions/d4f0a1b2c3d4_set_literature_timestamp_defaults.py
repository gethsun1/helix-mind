"""Set database defaults for Phase 3C literature timestamps.

Revision ID: d4f0a1b2c3d4
Revises: c7e9f8a1d2b3
"""

from alembic import op
import sqlalchemy as sa


revision = "d4f0a1b2c3d4"
down_revision = "c7e9f8a1d2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("papers", "retrieved_at", server_default=sa.text("now()"))
    op.alter_column("papers", "updated_at", server_default=sa.text("now()"))
    op.alter_column("investigation_papers", "discovered_at", server_default=sa.text("now()"))


def downgrade() -> None:
    op.alter_column("investigation_papers", "discovered_at", server_default=None)
    op.alter_column("papers", "updated_at", server_default=None)
    op.alter_column("papers", "retrieved_at", server_default=None)
