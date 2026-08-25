"""Add Phase 4A run, snapshot, and artifact contracts."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c1d2e3f4g5h6"
down_revision = "b8d9e0f1g2h3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    json_type = postgresql.JSONB(astext_type=sa.Text())

    op.create_table(
        "investigation_runs",
        sa.Column("investigation_id", uuid_type, nullable=False),
        sa.Column("parent_run_id", uuid_type, nullable=True),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="QUEUED", nullable=False),
        sa.Column("code_version", sa.String(length=128), server_default="unknown", nullable=False),
        sa.Column("schema_version", sa.String(length=64), server_default="phase4a-1", nullable=False),
        sa.Column("plan_hash", sa.String(length=64), nullable=True),
        sa.Column("input_manifest", json_type, nullable=True),
        sa.Column("provider_metadata", json_type, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", uuid_type, nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_run_id"], ["investigation_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("investigation_id", "run_number", name="uq_investigation_runs_number"),
    )
    op.create_index("ix_investigation_runs_investigation_id", "investigation_runs", ["investigation_id"])
    op.create_index("ix_investigation_runs_parent_run_id", "investigation_runs", ["parent_run_id"])
    op.create_index("ix_investigation_runs_investigation_created", "investigation_runs", ["investigation_id", "created_at"])

    op.create_table(
        "research_snapshots",
        sa.Column("investigation_id", uuid_type, nullable=False),
        sa.Column("run_id", uuid_type, nullable=False),
        sa.Column("created_by_user_id", uuid_type, nullable=True),
        sa.Column("snapshot_number", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=64), server_default="phase4a-1", nullable=False),
        sa.Column("formula_version", sa.String(length=64), nullable=True),
        sa.Column("metta_digest", sa.String(length=64), nullable=True),
        sa.Column("manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("manifest", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", uuid_type, nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["investigation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("investigation_id", "snapshot_number", name="uq_research_snapshots_number"),
        sa.UniqueConstraint("run_id", name="uq_research_snapshots_run"),
    )
    op.create_index("ix_research_snapshots_investigation_id", "research_snapshots", ["investigation_id"])
    op.create_index("ix_research_snapshots_run_id", "research_snapshots", ["run_id"])
    op.create_index("ix_research_snapshots_manifest_digest", "research_snapshots", ["manifest_digest"])
    op.create_index("ix_research_snapshots_investigation_created", "research_snapshots", ["investigation_id", "created_at"])

    op.create_table(
        "research_artifacts",
        sa.Column("snapshot_id", uuid_type, nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("artifact_format", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="PLANNED", nullable=False),
        sa.Column("generator_version", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=64), server_default="phase4a-1", nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=True),
        sa.Column("manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("metadata", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", uuid_type, nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["research_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "artifact_type", "artifact_format", "generator_version", name="uq_research_artifacts_contract"),
    )
    op.create_index("ix_research_artifacts_snapshot_id", "research_artifacts", ["snapshot_id"])
    op.create_index("ix_research_artifacts_snapshot_created", "research_artifacts", ["snapshot_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_research_artifacts_snapshot_created", table_name="research_artifacts")
    op.drop_index("ix_research_artifacts_snapshot_id", table_name="research_artifacts")
    op.drop_table("research_artifacts")
    op.drop_index("ix_research_snapshots_investigation_created", table_name="research_snapshots")
    op.drop_index("ix_research_snapshots_manifest_digest", table_name="research_snapshots")
    op.drop_index("ix_research_snapshots_run_id", table_name="research_snapshots")
    op.drop_index("ix_research_snapshots_investigation_id", table_name="research_snapshots")
    op.drop_table("research_snapshots")
    op.drop_index("ix_investigation_runs_investigation_created", table_name="investigation_runs")
    op.drop_index("ix_investigation_runs_parent_run_id", table_name="investigation_runs")
    op.drop_index("ix_investigation_runs_investigation_id", table_name="investigation_runs")
    op.drop_table("investigation_runs")
