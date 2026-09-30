"""Add private scientific asset provenance and rights records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f1a2b3c4d5e6"
down_revision = "9a0b1c2d3e4f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uid = postgresql.UUID(as_uuid=True)
    js = postgresql.JSONB(astext_type=sa.Text())
    op.create_table("scientific_assets",
        sa.Column("investigation_id", uid, nullable=False), sa.Column("created_by_user_id", uid, nullable=False),
        sa.Column("asset_type", sa.String(64), nullable=False), sa.Column("title", sa.String(255), nullable=False),
        sa.Column("visibility", sa.String(16), server_default="PRIVATE", nullable=False), sa.Column("status", sa.String(32), server_default="DRAFT", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", uid, nullable=False), sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_scientific_assets_investigation_id", "scientific_assets", ["investigation_id"])
    op.create_index("ix_scientific_assets_investigation_created", "scientific_assets", ["investigation_id", "created_at"])
    op.create_table("asset_versions",
        sa.Column("asset_id", uid, nullable=False), sa.Column("version_number", sa.Integer(), nullable=False), sa.Column("parent_version_id", uid, nullable=True),
        sa.Column("investigation_id", uid, nullable=False), sa.Column("snapshot_id", uid, nullable=False), sa.Column("artifact_id", uid, nullable=False),
        sa.Column("snapshot_manifest_digest", sa.String(64), nullable=False), sa.Column("artifact_content_digest", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(64), server_default="asset-manifest-1", nullable=False), sa.Column("canonicalization_version", sa.String(64), server_default="asset-canonical-json-1", nullable=False),
        sa.Column("scientific_status", js, nullable=False), sa.Column("status", sa.String(32), server_default="DRAFT", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("id", uid, nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["scientific_assets.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["parent_version_id"], ["asset_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["snapshot_id"], ["research_snapshots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["artifact_id"], ["research_artifacts.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("asset_id", "version_number", name="uq_asset_versions_number"))
    for col in ("asset_id", "investigation_id"):
        op.create_index(f"ix_asset_versions_{col}", "asset_versions", [col])
    op.create_index("ix_asset_versions_asset_created", "asset_versions", ["asset_id", "created_at"])
    op.create_table("asset_rights_declarations",
        sa.Column("asset_version_id", uid, nullable=False), sa.Column("declaration_actor_id", uid, nullable=False), sa.Column("declared_owner", js, nullable=False),
        sa.Column("contributors", js, nullable=False), sa.Column("ownership_basis", sa.Text(), nullable=False), sa.Column("rights_scope", sa.Text(), nullable=False),
        sa.Column("license_declaration", js, nullable=False), sa.Column("third_party_material", js, nullable=False), sa.Column("intended_use", sa.String(64), nullable=False),
        sa.Column("visibility", sa.String(16), server_default="PRIVATE", nullable=False), sa.Column("rights_status", sa.String(24), server_default="DECLARED", nullable=False),
        sa.Column("conflict_status", sa.String(24), server_default="NONE_DECLARED", nullable=False), sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("declared_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("id", uid, nullable=False),
        sa.ForeignKeyConstraint(["asset_version_id"], ["asset_versions.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["declaration_actor_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_asset_rights_declarations_asset_version_id", "asset_rights_declarations", ["asset_version_id"])
    op.create_index("ix_asset_rights_version_created", "asset_rights_declarations", ["asset_version_id", "declared_at"])
    op.create_table("asset_events",
        sa.Column("asset_id", uid, nullable=False), sa.Column("asset_version_id", uid, nullable=True), sa.Column("actor_id", uid, nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False), sa.Column("reason", sa.Text(), nullable=True), sa.Column("previous_status", sa.String(32), nullable=True),
        sa.Column("new_status", sa.String(32), nullable=True), sa.Column("metadata", js, nullable=False), sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("id", uid, nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["scientific_assets.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["asset_version_id"], ["asset_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_asset_events_asset_id", "asset_events", ["asset_id"])
    op.create_index("ix_asset_events_asset_timestamp", "asset_events", ["asset_id", "timestamp"])


def downgrade() -> None:
    op.drop_table("asset_events")
    op.drop_table("asset_rights_declarations")
    op.drop_table("asset_versions")
    op.drop_table("scientific_assets")
