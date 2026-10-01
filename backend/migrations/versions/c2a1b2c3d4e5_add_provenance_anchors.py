"""Add private C2 provenance anchor records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c2a1b2c3d4e5"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uid = postgresql.UUID(as_uuid=True)
    js = postgresql.JSONB(astext_type=sa.Text())
    op.create_table("asset_provenance_anchors",
        sa.Column("scientific_asset_id", uid, nullable=False),
        sa.Column("asset_version_id", uid, nullable=False),
        sa.Column("canonical_provenance_digest", sa.String(64), nullable=False),
        sa.Column("anchor_provider", sa.String(64), nullable=False),
        sa.Column("anchor_type", sa.String(64), nullable=False),
        sa.Column("external_reference", sa.String(255), nullable=False),
        sa.Column("anchor_status", sa.String(24), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_metadata", js, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("provider_metadata", js, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by_user_id", uid, nullable=False),
        sa.Column("error_category", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", uid, nullable=False),
        sa.ForeignKeyConstraint(["scientific_asset_id"], ["scientific_assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["asset_version_id"], ["asset_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_version_id", "canonical_provenance_digest", "anchor_provider", name="uq_asset_anchor_version_digest_provider"))
    op.create_index("ix_asset_provenance_anchors_scientific_asset_id", "asset_provenance_anchors", ["scientific_asset_id"])
    op.create_index("ix_asset_provenance_anchors_asset_version_id", "asset_provenance_anchors", ["asset_version_id"])
    op.create_index("ix_asset_anchor_asset_version", "asset_provenance_anchors", ["scientific_asset_id", "asset_version_id"])


def downgrade() -> None:
    op.drop_table("asset_provenance_anchors")
