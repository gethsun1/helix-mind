"""Add provenance-preserving scientific knowledge structures."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a7c8d9e0f1g2"
down_revision = "f6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entities", sa.Column("normalized_name", sa.String(length=512), nullable=True))
    op.add_column("entities", sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("entities", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True))
    op.add_column("entities", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True))
    op.execute("UPDATE entities SET normalized_name = lower(regexp_replace(trim(canonical_name), '[^[:alnum:]]+', ' ', 'g')) WHERE normalized_name IS NULL")
    op.alter_column("entities", "normalized_name", nullable=False)
    op.alter_column("entities", "created_at", nullable=False)
    op.alter_column("entities", "updated_at", nullable=False)
    op.drop_index("ix_entities_type_canonical_name", table_name="entities")
    op.create_index("ix_entities_type_normalized_name", "entities", ["entity_type", "normalized_name"], unique=True)

    op.create_table(
        "claims",
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paper_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("claim_hash", sa.String(length=64), nullable=False),
        sa.Column("extraction_method", sa.String(length=64), server_default="deterministic_abstract", nullable=False),
        sa.Column("extraction_confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("investigation_id", "claim_hash", name="uq_claims_investigation_hash"),
    )
    op.create_index("ix_claims_investigation_created", "claims", ["investigation_id", "created_at"])
    op.create_index("ix_claims_paper_id", "claims", ["paper_id"])

    op.add_column("relationships", sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("relationships", sa.Column("stance", sa.String(length=24), server_default="SUPPORTS", nullable=False))
    op.create_foreign_key("fk_relationships_investigation", "relationships", "investigations", ["investigation_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_relationships_investigation_id", "relationships", ["investigation_id"])

    op.add_column("evidence", sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("evidence", sa.Column("source_location", sa.String(length=64), server_default="abstract", nullable=False))
    op.add_column("evidence", sa.Column("source_span", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("evidence", sa.Column("section", sa.String(length=255), nullable=True))
    op.add_column("evidence", sa.Column("retrieval_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("evidence", sa.Column("extraction_timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_foreign_key("fk_evidence_investigation", "evidence", "investigations", ["investigation_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_evidence_investigation_id", "evidence", ["investigation_id"])

    op.create_table(
        "claim_evidence",
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=24), server_default="DIRECT", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id", "evidence_id", name="uq_claim_evidence_pair"),
    )
    op.create_index("ix_claim_evidence_claim_id", "claim_evidence", ["claim_id"])
    op.create_index("ix_claim_evidence_evidence_id", "claim_evidence", ["evidence_id"])

    op.create_table(
        "claim_entities",
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=24), server_default="MENTIONS", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id", "entity_id", name="uq_claim_entity_pair"),
    )
    op.create_index("ix_claim_entities_claim_id", "claim_entities", ["claim_id"])
    op.create_index("ix_claim_entities_entity_id", "claim_entities", ["entity_id"])

    op.create_table(
        "relationship_claims",
        sa.Column("relationship_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["relationship_id"], ["relationships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("relationship_id", "claim_id", name="uq_relationship_claim_pair"),
    )
    op.create_index("ix_relationship_claims_relationship_id", "relationship_claims", ["relationship_id"])
    op.create_index("ix_relationship_claims_claim_id", "relationship_claims", ["claim_id"])


def downgrade() -> None:
    op.drop_table("relationship_claims")
    op.drop_table("claim_entities")
    op.drop_table("claim_evidence")
    op.drop_index("ix_evidence_investigation_id", table_name="evidence")
    op.drop_constraint("fk_evidence_investigation", "evidence", type_="foreignkey")
    for column in ("extraction_timestamp", "retrieval_metadata", "section", "source_span", "source_location", "investigation_id"):
        op.drop_column("evidence", column)
    op.drop_index("ix_relationships_investigation_id", table_name="relationships")
    op.drop_constraint("fk_relationships_investigation", "relationships", type_="foreignkey")
    op.drop_column("relationships", "stance")
    op.drop_column("relationships", "investigation_id")
    op.drop_index("ix_claims_paper_id", table_name="claims")
    op.drop_index("ix_claims_investigation_created", table_name="claims")
    op.drop_table("claims")
    op.drop_index("ix_entities_type_normalized_name", table_name="entities")
    op.create_index("ix_entities_type_canonical_name", "entities", ["entity_type", "canonical_name"], unique=True)
    for column in ("updated_at", "created_at", "aliases", "normalized_name"):
        op.drop_column("entities", column)
