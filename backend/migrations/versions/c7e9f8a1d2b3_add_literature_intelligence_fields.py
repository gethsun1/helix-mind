"""Add Phase 3C literature provenance, searches, and ranking fields.

Revision ID: c7e9f8a1d2b3
Revises: b21d7abf3c4e
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c7e9f8a1d2b3"
down_revision = "b21d7abf3c4e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("papers", sa.Column("journal", sa.String(length=512), nullable=True))
    op.add_column("papers", sa.Column("publication_type", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("papers", sa.Column("language", sa.String(length=32), nullable=True))
    op.add_column("papers", sa.Column("mesh_terms", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("papers", sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("papers", sa.Column("pmid", sa.String(length=64), nullable=True))
    op.add_column("papers", sa.Column("pmcid", sa.String(length=64), nullable=True))
    op.add_column("papers", sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("papers", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE papers SET source = CASE WHEN lower(source) = 'europepmc' THEN 'EUROPE_PMC' ELSE upper(source) END")
    op.execute("UPDATE papers SET pmid = CASE WHEN source = 'PUBMED' THEN external_id ELSE metadata->>'pmid' END")
    op.execute("UPDATE papers SET pmcid = CASE WHEN source = 'EUROPE_PMC' THEN metadata->>'europe_pmc_id' ELSE NULL END")
    op.execute("UPDATE papers SET journal = metadata->>'journal'")
    op.execute("UPDATE papers SET retrieved_at = created_at WHERE retrieved_at IS NULL")
    op.execute("UPDATE papers SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("papers", "retrieved_at", nullable=False)
    op.alter_column("papers", "updated_at", nullable=False)
    op.create_index("ix_papers_doi_unique", "papers", ["doi"], unique=True, postgresql_where=sa.text("doi IS NOT NULL"))
    op.create_index("ix_papers_pmid_unique", "papers", ["pmid"], unique=True, postgresql_where=sa.text("pmid IS NOT NULL"))
    op.create_index("ix_papers_pmcid_unique", "papers", ["pmcid"], unique=True, postgresql_where=sa.text("pmcid IS NOT NULL"))

    op.create_table(
        "research_searches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cache_key", sa.String(length=512), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("result_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("reused", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_searches_investigation_id", "research_searches", ["investigation_id"], unique=False)
    op.create_index("ix_research_searches_investigation_executed", "research_searches", ["investigation_id", "executed_at"], unique=False)
    op.create_index("ix_research_searches_cache_key", "research_searches", ["investigation_id", "source", "cache_key"], unique=False)

    op.add_column("investigation_papers", sa.Column("source", sa.String(length=32), nullable=True))
    op.add_column("investigation_papers", sa.Column("research_search_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("investigation_papers", sa.Column("relevance_score", sa.Numeric(precision=6, scale=4), nullable=True))
    op.add_column("investigation_papers", sa.Column("relevance_reason", sa.Text(), nullable=True))
    op.add_column("investigation_papers", sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("investigation_papers", sa.Column("selected", sa.Boolean(), server_default=sa.text("false"), nullable=True))
    op.add_column("investigation_papers", sa.Column("rank", sa.Integer(), nullable=True))
    op.execute("UPDATE investigation_papers ip SET source = p.source, discovered_at = ip.created_at FROM papers p WHERE p.id = ip.paper_id")
    op.execute("UPDATE investigation_papers SET discovered_at = now() WHERE discovered_at IS NULL")
    op.execute("UPDATE investigation_papers SET selected = false WHERE selected IS NULL")
    op.alter_column("investigation_papers", "source", nullable=False)
    op.alter_column("investigation_papers", "discovered_at", nullable=False)
    op.alter_column("investigation_papers", "selected", nullable=False)
    op.create_foreign_key("fk_investigation_papers_research_search", "investigation_papers", "research_searches", ["research_search_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_investigation_papers_research_search_id", "investigation_papers", ["research_search_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_investigation_papers_research_search_id", table_name="investigation_papers")
    op.drop_constraint("fk_investigation_papers_research_search", "investigation_papers", type_="foreignkey")
    for column in ("rank", "selected", "discovered_at", "relevance_reason", "relevance_score", "research_search_id", "source"):
        op.drop_column("investigation_papers", column)
    op.drop_index("ix_research_searches_cache_key", table_name="research_searches")
    op.drop_index("ix_research_searches_investigation_executed", table_name="research_searches")
    op.drop_index("ix_research_searches_investigation_id", table_name="research_searches")
    op.drop_table("research_searches")
    op.drop_index("ix_papers_pmcid_unique", table_name="papers")
    op.drop_index("ix_papers_pmid_unique", table_name="papers")
    op.drop_index("ix_papers_doi_unique", table_name="papers")
    for column in ("updated_at", "retrieved_at", "pmcid", "pmid", "keywords", "mesh_terms", "language", "publication_type", "journal"):
        op.drop_column("papers", column)
