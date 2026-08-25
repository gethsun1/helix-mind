"""Add additive Phase 3E scientific reasoning structures."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b8d9e0f1g2h3"
down_revision = "a7c8d9e0f1g2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    json_type = postgresql.JSONB(astext_type=sa.Text())

    op.create_table(
        "propositions",
        sa.Column("investigation_id", uuid_type, nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("predicate", sa.String(length=128), nullable=False),
        sa.Column("object", sa.String(length=512), nullable=False),
        sa.Column("normalized_subject", sa.String(length=512), nullable=False),
        sa.Column("normalized_predicate", sa.String(length=128), nullable=False),
        sa.Column("normalized_object", sa.String(length=512), nullable=False),
        sa.Column("proposition_key", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("context", json_type, nullable=True),
        sa.Column("provenance", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", uuid_type, nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("investigation_id", "proposition_key", name="uq_propositions_investigation_key"),
    )
    op.create_index("ix_propositions_investigation", "propositions", ["investigation_id"])

    op.add_column("claims", sa.Column("proposition_id", uuid_type, nullable=True))
    op.create_foreign_key("fk_claims_proposition", "claims", "propositions", ["proposition_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_claims_proposition_id", "claims", ["proposition_id"])

    op.add_column("evidence", sa.Column("proposition_id", uuid_type, nullable=True))
    op.add_column("evidence", sa.Column("polarity", sa.String(length=24), nullable=True))
    op.add_column("evidence", sa.Column("extraction_method", sa.String(length=64), nullable=True))
    op.create_foreign_key("fk_evidence_proposition", "evidence", "propositions", ["proposition_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_evidence_proposition_id", "evidence", ["proposition_id"])

    op.add_column("hypotheses", sa.Column("proposition_id", uuid_type, nullable=True))
    op.add_column("hypotheses", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("hypotheses", sa.Column("supporting_evidence_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("hypotheses", sa.Column("contradictory_evidence_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("hypotheses", sa.Column("uncertainty", json_type, nullable=True))
    op.add_column("hypotheses", sa.Column("provenance", json_type, nullable=True))
    op.add_column("hypotheses", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_foreign_key("fk_hypotheses_proposition", "hypotheses", "propositions", ["proposition_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_hypotheses_proposition_id", "hypotheses", ["proposition_id"])

    op.add_column("inferences", sa.Column("rule_name", sa.String(length=64), server_default="direct_evidence_balance", nullable=False))

    op.add_column("knowledge_gaps", sa.Column("hypothesis_id", uuid_type, nullable=True))
    op.add_column("knowledge_gaps", sa.Column("proposition_id", uuid_type, nullable=True))
    op.add_column("knowledge_gaps", sa.Column("evidence_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("knowledge_gaps", sa.Column("contradiction_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("knowledge_gaps", sa.Column("confidence", sa.Numeric(precision=4, scale=3), server_default="0", nullable=False))
    op.add_column("knowledge_gaps", sa.Column("rationale", sa.Text(), nullable=True))
    op.add_column("knowledge_gaps", sa.Column("research_opportunity", sa.Text(), nullable=True))
    op.add_column("knowledge_gaps", sa.Column("related_entity_ids", json_type, nullable=True))
    op.add_column("knowledge_gaps", sa.Column("provenance", json_type, nullable=True))
    op.create_foreign_key("fk_knowledge_gaps_hypothesis", "knowledge_gaps", "hypotheses", ["hypothesis_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_knowledge_gaps_proposition", "knowledge_gaps", "propositions", ["proposition_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_knowledge_gaps_hypothesis_id", "knowledge_gaps", ["hypothesis_id"])
    op.create_index("ix_knowledge_gaps_proposition_id", "knowledge_gaps", ["proposition_id"])

    op.create_table(
        "contradictions",
        sa.Column("investigation_id", uuid_type, nullable=False),
        sa.Column("proposition_id", uuid_type, nullable=False),
        sa.Column("supporting_evidence_id", uuid_type, nullable=False),
        sa.Column("contradictory_evidence_id", uuid_type, nullable=False),
        sa.Column("contradiction_type", sa.String(length=32), nullable=False),
        sa.Column("context", json_type, nullable=True),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("provenance", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", uuid_type, nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["proposition_id"], ["propositions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supporting_evidence_id"], ["evidence.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contradictory_evidence_id"], ["evidence.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("investigation_id", "proposition_id", "supporting_evidence_id", "contradictory_evidence_id", name="uq_contradiction_evidence_pair"),
    )
    op.create_index("ix_contradictions_investigation", "contradictions", ["investigation_id"])


def downgrade() -> None:
    op.drop_index("ix_contradictions_investigation", table_name="contradictions")
    op.drop_table("contradictions")
    for name in ("ix_knowledge_gaps_proposition_id", "ix_knowledge_gaps_hypothesis_id"):
        op.drop_index(name, table_name="knowledge_gaps")
    op.drop_constraint("fk_knowledge_gaps_proposition", "knowledge_gaps", type_="foreignkey")
    op.drop_constraint("fk_knowledge_gaps_hypothesis", "knowledge_gaps", type_="foreignkey")
    for column in ("provenance", "related_entity_ids", "research_opportunity", "rationale", "confidence", "contradiction_count", "evidence_count", "proposition_id", "hypothesis_id"):
        op.drop_column("knowledge_gaps", column)
    op.drop_column("inferences", "rule_name")
    op.drop_index("ix_hypotheses_proposition_id", table_name="hypotheses")
    op.drop_constraint("fk_hypotheses_proposition", "hypotheses", type_="foreignkey")
    for column in ("updated_at", "provenance", "uncertainty", "contradictory_evidence_count", "supporting_evidence_count", "description", "proposition_id"):
        op.drop_column("hypotheses", column)
    op.drop_index("ix_evidence_proposition_id", table_name="evidence")
    op.drop_constraint("fk_evidence_proposition", "evidence", type_="foreignkey")
    for column in ("extraction_method", "polarity", "proposition_id"):
        op.drop_column("evidence", column)
    op.drop_index("ix_claims_proposition_id", table_name="claims")
    op.drop_constraint("fk_claims_proposition", "claims", type_="foreignkey")
    op.drop_column("claims", "proposition_id")
    op.drop_index("ix_propositions_investigation", table_name="propositions")
    op.drop_table("propositions")
