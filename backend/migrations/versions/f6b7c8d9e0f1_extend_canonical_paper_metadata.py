"""Extend canonical papers with explicit publication metadata."""

from alembic import op
import sqlalchemy as sa


revision = "f6b7c8d9e0f1"
down_revision = "e5a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("papers", sa.Column("full_text_url", sa.Text(), nullable=True))
    op.add_column("papers", sa.Column("publisher_identifier", sa.String(length=255), nullable=True))
    op.add_column("papers", sa.Column("journal_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("papers", "journal_metadata")
    op.drop_column("papers", "publisher_identifier")
    op.drop_column("papers", "full_text_url")
