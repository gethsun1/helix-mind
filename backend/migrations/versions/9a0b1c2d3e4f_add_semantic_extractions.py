"""Add investigation-scoped candidate semantic extractions.

Revision ID: 9a0b1c2d3e4f
Revises: 8a2c4e6f0b11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "9a0b1c2d3e4f"
down_revision = "8a2c4e6f0b11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_span", sa.Text(), nullable=True),
        sa.Column("source_locator", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("semantic_type", sa.String(length=48), nullable=True),
        sa.Column("relation_type", sa.String(length=48), nullable=True),
        sa.Column("extraction_version", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("extraction_status", sa.String(length=24), nullable=False),
        sa.Column("validation_status", sa.String(length=24), nullable=False),
        sa.Column("validation_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("graph_relationship_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_run_id"], ["investigation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["investigation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["publication_id"], ["papers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["graph_relationship_id"], ["relationships.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("investigation_id", "content_hash", name="uq_semantic_extractions_content"),
    )
    op.create_index("ix_semantic_extractions_investigation_id", "semantic_extractions", ["investigation_id"])
    op.create_index("ix_semantic_extractions_investigation_created", "semantic_extractions", ["investigation_id", "created_at"])
    op.create_index("ix_semantic_extractions_evidence", "semantic_extractions", ["evidence_id"])


def downgrade() -> None:
    op.drop_index("ix_semantic_extractions_evidence", table_name="semantic_extractions")
    op.drop_index("ix_semantic_extractions_investigation_created", table_name="semantic_extractions")
    op.drop_index("ix_semantic_extractions_investigation_id", table_name="semantic_extractions")
    op.drop_table("semantic_extractions")
