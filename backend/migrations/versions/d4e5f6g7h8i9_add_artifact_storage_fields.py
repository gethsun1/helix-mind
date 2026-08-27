"""Add private storage and lifecycle fields to research artifacts."""

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6g7h8i9"
down_revision = "c1d2e3f4g5h6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("research_artifacts", sa.Column("content_type", sa.String(length=128), nullable=True))
    op.add_column("research_artifacts", sa.Column("file_size", sa.BigInteger(), nullable=True))
    op.add_column("research_artifacts", sa.Column("storage_key", sa.Text(), nullable=True))
    op.add_column("research_artifacts", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("research_artifacts", sa.Column("visibility", sa.String(length=16), server_default="PRIVATE", nullable=False))
    op.add_column("research_artifacts", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("research_artifacts", "completed_at")
    op.drop_column("research_artifacts", "visibility")
    op.drop_column("research_artifacts", "error_message")
    op.drop_column("research_artifacts", "storage_key")
    op.drop_column("research_artifacts", "file_size")
    op.drop_column("research_artifacts", "content_type")
