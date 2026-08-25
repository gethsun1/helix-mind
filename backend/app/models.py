import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class User(UUIDPrimaryKey, Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email", unique=True),)

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="USER", server_default="USER")
    provider_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    research_focus: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Investigation(UUIDPrimaryKey, Base):
    __tablename__ = "investigations"
    __table_args__ = (Index("ix_investigations_status_created_at", "status", "created_at"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Scientific investigation", server_default="Scientific investigation")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, default="biotechnology", server_default="biotechnology")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED", server_default="QUEUED")
    research_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    synthesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class InvestigationEvent(UUIDPrimaryKey, Base):
    __tablename__ = "investigation_events"
    __table_args__ = (Index("ix_investigation_events_investigation_timestamp", "investigation_id", "timestamp"),)

    investigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InvestigationRun(UUIDPrimaryKey, Base):
    """Immutable execution identity for one investigation attempt."""

    __tablename__ = "investigation_runs"
    __table_args__ = (
        UniqueConstraint("investigation_id", "run_number", name="uq_investigation_runs_number"),
        Index("ix_investigation_runs_investigation_created", "investigation_id", "created_at"),
    )

    investigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("investigation_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED", server_default="QUEUED")
    code_version: Mapped[str] = mapped_column(String(128), nullable=False, default="unknown", server_default="unknown")
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False, default="phase4a-1", server_default="phase4a-1")
    plan_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_manifest: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ResearchSnapshot(UUIDPrimaryKey, Base):
    """Immutable manifest of one investigation run and its source graph."""

    __tablename__ = "research_snapshots"
    __table_args__ = (
        UniqueConstraint("investigation_id", "snapshot_number", name="uq_research_snapshots_number"),
        UniqueConstraint("run_id", name="uq_research_snapshots_run"),
        Index("ix_research_snapshots_investigation_created", "investigation_id", "created_at"),
    )

    investigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigation_runs.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    snapshot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False, default="phase4a-1", server_default="phase4a-1")
    formula_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metta_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ResearchArtifact(UUIDPrimaryKey, Base):
    """Registry contract for a future artifact generated from a snapshot."""

    __tablename__ = "research_artifacts"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "artifact_type", "artifact_format", "generator_version", name="uq_research_artifacts_contract"),
        Index("ix_research_artifacts_snapshot_created", "snapshot_id", "created_at"),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_snapshots.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_format: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PLANNED", server_default="PLANNED")
    generator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False, default="phase4a-1", server_default="phase4a-1")
    content_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Paper(UUIDPrimaryKey, Base):
    __tablename__ = "papers"
    __table_args__ = (
        Index("ix_papers_source_external_id", "source", "external_id", unique=True),
        Index("ix_papers_doi_unique", "doi", unique=True, postgresql_where=text("doi IS NOT NULL")),
        Index("ix_papers_pmid_unique", "pmid", unique=True, postgresql_where=text("pmid IS NOT NULL")),
        Index("ix_papers_pmcid_unique", "pmcid", unique=True, postgresql_where=text("pmcid IS NOT NULL")),
    )

    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    authors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    journal: Mapped[str | None] = mapped_column(String(512), nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    publication_type: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mesh_terms: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    pmid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pmcid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publisher_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    journal_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    paper_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now(), nullable=False)


class InvestigationPaper(UUIDPrimaryKey, Base):
    """Provenance-preserving association between an investigation and a paper."""

    __tablename__ = "investigation_papers"
    __table_args__ = (UniqueConstraint("investigation_id", "paper_id", name="uq_investigation_papers_pair"),)

    investigation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True)
    source_query: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    research_search_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("research_searches.id", ondelete="SET NULL"), nullable=True, index=True)
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    relevance_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ResearchSearch(UUIDPrimaryKey, Base):
    __tablename__ = "research_searches"
    __table_args__ = (
        Index("ix_research_searches_investigation_executed", "investigation_id", "executed_at"),
        Index("ix_research_searches_cache_key", "investigation_id", "source", "cache_key"),
    )

    investigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cache_key: Mapped[str] = mapped_column(String(512), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    reused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class Entity(UUIDPrimaryKey, Base):
    __tablename__ = "entities"
    __table_args__ = (Index("ix_entities_type_normalized_name", "entity_type", "normalized_name", unique=True),)

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(512), nullable=False)
    aliases: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Claim(UUIDPrimaryKey, Base):
    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("investigation_id", "claim_hash", name="uq_claims_investigation_hash"),
        Index("ix_claims_investigation_created", "investigation_id", "created_at"),
    )

    investigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True)
    proposition_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("propositions.id", ondelete="SET NULL"), nullable=True, index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False, default="deterministic_abstract", server_default="deterministic_abstract")
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    claim_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Relationship(UUIDPrimaryKey, Base):
    __tablename__ = "relationships"
    __table_args__ = (Index("ix_relationships_predicate", "predicate"),)

    investigation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), nullable=True, index=True)
    subject_entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    predicate: Mapped[str] = mapped_column(String(64), nullable=False)
    object_entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    strength: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    stance: Mapped[str] = mapped_column(String(24), nullable=False, default="SUPPORTS", server_default="SUPPORTS")
    relationship_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)


class Evidence(UUIDPrimaryKey, Base):
    __tablename__ = "evidence"
    __table_args__ = (Index("ix_evidence_relationship_id", "relationship_id"),)

    investigation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), nullable=True, index=True)
    paper_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("papers.id", ondelete="SET NULL"), nullable=True)
    proposition_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("propositions.id", ondelete="SET NULL"), nullable=True, index=True)
    source_location: Mapped[str] = mapped_column(String(64), nullable=False, default="abstract", server_default="abstract")
    source_span: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retrieval_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extraction_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    relationship_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("relationships.id", ondelete="SET NULL"), nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    strength: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    polarity: Mapped[str | None] = mapped_column(String(24), nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)


class ClaimEvidence(UUIDPrimaryKey, Base):
    __tablename__ = "claim_evidence"
    __table_args__ = (UniqueConstraint("claim_id", "evidence_id", name="uq_claim_evidence_pair"),)

    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(24), nullable=False, default="DIRECT", server_default="DIRECT")


class ClaimEntity(UUIDPrimaryKey, Base):
    __tablename__ = "claim_entities"
    __table_args__ = (UniqueConstraint("claim_id", "entity_id", name="uq_claim_entity_pair"),)

    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(24), nullable=False, default="MENTIONS", server_default="MENTIONS")


class RelationshipClaim(UUIDPrimaryKey, Base):
    __tablename__ = "relationship_claims"
    __table_args__ = (UniqueConstraint("relationship_id", "claim_id", name="uq_relationship_claim_pair"),)

    relationship_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("relationships.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True)


class Hypothesis(UUIDPrimaryKey, Base):
    __tablename__ = "hypotheses"
    __table_args__ = (Index("ix_hypotheses_investigation_status", "investigation_id", "status"),)

    investigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    proposition_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("propositions.id", ondelete="SET NULL"), nullable=True, index=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    strength: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    supporting_evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    contradictory_evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    uncertainty: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    provenance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Inference(UUIDPrimaryKey, Base):
    __tablename__ = "inferences"

    hypothesis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(64), nullable=False, default="direct_evidence_balance", server_default="direct_evidence_balance")
    reasoning_summary: Mapped[str] = mapped_column(Text, nullable=False)
    strength: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    inference_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KnowledgeGap(UUIDPrimaryKey, Base):
    __tablename__ = "knowledge_gaps"

    investigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    hypothesis_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hypotheses.id", ondelete="SET NULL"), nullable=True, index=True)
    proposition_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("propositions.id", ondelete="SET NULL"), nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    contradiction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, default=Decimal("0"), server_default="0")
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_opportunity: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_entity_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    provenance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Proposition(UUIDPrimaryKey, Base):
    """Stable structured scientific proposition derived from source-linked claims."""

    __tablename__ = "propositions"
    __table_args__ = (
        UniqueConstraint("investigation_id", "proposition_key", name="uq_propositions_investigation_key"),
        Index("ix_propositions_investigation", "investigation_id"),
    )

    investigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    predicate: Mapped[str] = mapped_column(String(128), nullable=False)
    object: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_predicate: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_object: Mapped[str] = mapped_column(String(512), nullable=False)
    proposition_key: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    provenance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Contradiction(UUIDPrimaryKey, Base):
    """Explicit opposing evidence pair; never inferred from paper titles alone."""

    __tablename__ = "contradictions"
    __table_args__ = (
        UniqueConstraint("investigation_id", "proposition_id", "supporting_evidence_id", "contradictory_evidence_id", name="uq_contradiction_evidence_pair"),
        Index("ix_contradictions_investigation", "investigation_id"),
    )

    investigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    proposition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("propositions.id", ondelete="CASCADE"), nullable=False)
    supporting_evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False)
    contradictory_evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False)
    contradiction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    provenance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentRun(UUIDPrimaryKey, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_investigation_status", "investigation_id", "status"),)

    investigation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    agent: Mapped[str] = mapped_column(String(128), nullable=False)
    skill: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    run_input: Mapped[dict | None] = mapped_column("input", JSONB, nullable=True)
    run_output: Mapped[dict | None] = mapped_column("output", JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
