"""add explicit persistent research memories"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "8a2c4e6f0b11"
down_revision = "d4e5f6g7h8i9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_memories",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_type", sa.String(48), nullable=False),
        sa.Column("decision_text", sa.Text(), nullable=False),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_run_id"], ["investigation_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_snapshot_id"], ["research_snapshots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_memories_owner_id", "research_memories", ["owner_id"])
    op.create_index("ix_research_memories_investigation_id", "research_memories", ["investigation_id"])
    op.create_index("ix_research_memories_owner_investigation_active", "research_memories", ["owner_id", "investigation_id", "active"])


def downgrade() -> None:
    op.drop_index("ix_research_memories_owner_investigation_active", table_name="research_memories")
    op.drop_index("ix_research_memories_investigation_id", table_name="research_memories")
    op.drop_index("ix_research_memories_owner_id", table_name="research_memories")
    op.drop_table("research_memories")
