"""add investigation paper provenance

Revision ID: 4e4f8e4d6f60
Revises: 9cc407dfbcb0
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "4e4f8e4d6f60"
down_revision = "9cc407dfbcb0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investigation_papers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paper_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_query", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("investigation_id", "paper_id", name="uq_investigation_papers_pair"),
    )
    op.create_index("ix_investigation_papers_investigation_id", "investigation_papers", ["investigation_id"])
    op.create_index("ix_investigation_papers_paper_id", "investigation_papers", ["paper_id"])


def downgrade() -> None:
    op.drop_index("ix_investigation_papers_paper_id", table_name="investigation_papers")
    op.drop_index("ix_investigation_papers_investigation_id", table_name="investigation_papers")
    op.drop_table("investigation_papers")
