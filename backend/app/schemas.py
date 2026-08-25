from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InvestigationCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    research_question: str = Field(min_length=10, max_length=5_000)
    domain: str = Field(default="biotechnology", min_length=2, max_length=64)

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def accept_json_aliases(cls, values):
        if isinstance(values, dict) and "research_question" not in values:
            values = dict(values)
            values["research_question"] = values.get("researchQuestion", values.get("question"))
        return values

    @model_validator(mode="after")
    def normalize(self) -> "InvestigationCreate":
        self.title = self.title.strip()
        self.research_question = self.research_question.strip()
        self.domain = self.domain.strip().lower()
        if len(self.title) < 3:
            raise ValueError("title must contain at least 3 non-whitespace characters")
        if len(self.research_question) < 10:
            raise ValueError("research_question must contain at least 10 non-whitespace characters")
        if len(self.domain) < 2:
            raise ValueError("domain must contain at least 2 non-whitespace characters")
        return self


class InvestigationCreated(BaseModel):
    id: UUID
    status: str
    created_at: datetime = Field(serialization_alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class InvestigationEventRead(BaseModel):
    id: UUID
    event_type: str = Field(serialization_alias="type")
    message: str
    metadata: dict | None
    timestamp: datetime = Field(serialization_alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class InvestigationRead(BaseModel):
    id: UUID
    owner_id: UUID = Field(serialization_alias="ownerId")
    title: str
    research_question: str = Field(serialization_alias="researchQuestion")
    domain: str
    status: str
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    completed_at: datetime | None = Field(default=None, serialization_alias="completedAt")
    error_message: str | None = Field(default=None, serialization_alias="errorMessage")
    research_plan: dict | None = Field(default=None, serialization_alias="researchPlan")
    events: list[InvestigationEventRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class InvestigationCancelResponse(BaseModel):
    id: UUID
    status: str


class InvestigationPlan(BaseModel):
    research_objectives: list[str]
    research_questions: list[str]
    search_strategies: list[str]
    key_concepts: list[str]
    evidence_categories: list[str]
    reasoning_tasks: list[str]
    phase: str
    source_note: str


class UserRead(BaseModel):
    id: UUID
    email: str
    name: str | None
    image: str | None
    role: str
    organization: str | None
    research_focus: str | None


class UserProfileUpdate(BaseModel):
    display_name: str = Field(alias="displayName", min_length=2, max_length=255)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("display_name must contain at least 2 non-whitespace characters")
        return value


class OAuthUserSync(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    name: str | None = Field(default=None, max_length=255)
    image: str | None = Field(default=None, max_length=2_000)
    provider_account_id: str | None = Field(default=None, max_length=255)


class PaperRead(BaseModel):
    id: UUID
    source: str
    external_id: str = Field(serialization_alias="externalId")
    title: str
    abstract: str | None
    authors: list | None
    journal: str | None
    publication_date: date | None
    publication_type: list | None = Field(serialization_alias="publicationType")
    language: str | None
    mesh_terms: list | None = Field(default=None, serialization_alias="meshTerms")
    keywords: list | None
    doi: str | None
    pmid: str | None
    pmcid: str | None
    url: str | None
    full_text_url: str | None = Field(default=None, serialization_alias="fullTextUrl")
    publisher_identifier: str | None = Field(default=None, serialization_alias="publisherIdentifier")
    journal_metadata: dict | None = Field(default=None, serialization_alias="journalMetadata")
    metadata: dict | None
    retrieved_at: datetime = Field(serialization_alias="retrievedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    source_records: list[str] = Field(default_factory=list, serialization_alias="sourceRecords")
    relevance_score: float | None = Field(default=None, serialization_alias="relevanceScore")
    relevance_reason: str | None = Field(default=None, serialization_alias="relevanceReason")
    source_query: str | None = Field(default=None, serialization_alias="sourceQuery")
    discovered_at: datetime | None = Field(default=None, serialization_alias="discoveredAt")
    selected: bool = False
    rank: int | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PaperInvestigationRead(BaseModel):
    id: UUID
    title: str
    relevance_score: float | None = Field(default=None, serialization_alias="relevanceScore")
    relevance_reason: str | None = Field(default=None, serialization_alias="relevanceReason")
    rank: int | None
    selected: bool

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PaperDetailRead(PaperRead):
    investigations: list[PaperInvestigationRead] = Field(default_factory=list)
    provenance: list[dict] = Field(default_factory=list)


class PaperPage(BaseModel):
    items: list[PaperRead]
    total: int
    page: int
    page_size: int = Field(serialization_alias="pageSize")
    page_count: int = Field(serialization_alias="pageCount")

    model_config = ConfigDict(populate_by_name=True)


class ResearchSearchRead(BaseModel):
    id: UUID
    source: str
    query: str
    filters: dict | None
    executed_at: datetime = Field(serialization_alias="executedAt")
    result_count: int = Field(serialization_alias="resultCount")
    status: str
    error_message: str | None = Field(default=None, serialization_alias="errorMessage")
    reused: bool

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class KnowledgeEntityRead(BaseModel):
    id: UUID
    canonical_name: str = Field(serialization_alias="canonicalName")
    normalized_name: str = Field(serialization_alias="normalizedName")
    entity_type: str = Field(serialization_alias="entityType")
    aliases: list | None
    description: str | None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class KnowledgeEvidenceRead(BaseModel):
    id: UUID
    paper_id: UUID | None = Field(serialization_alias="paperId")
    evidence_type: str = Field(serialization_alias="evidenceType")
    extracted_text: str = Field(serialization_alias="extractedText")
    source_location: str = Field(serialization_alias="sourceLocation")
    source_span: dict | None = Field(serialization_alias="sourceSpan")
    section: str | None
    extraction_timestamp: datetime = Field(serialization_alias="extractionTimestamp")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class KnowledgeClaimRead(BaseModel):
    id: UUID
    paper_id: UUID = Field(serialization_alias="paperId")
    claim_text: str = Field(serialization_alias="claimText")
    extraction_method: str = Field(serialization_alias="extractionMethod")
    extraction_confidence: float | None = Field(serialization_alias="extractionConfidence")
    evidence: list[KnowledgeEvidenceRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class KnowledgeRelationshipRead(BaseModel):
    id: UUID
    subject_entity_id: UUID = Field(serialization_alias="subjectEntityId")
    predicate: str
    object_entity_id: UUID = Field(serialization_alias="objectEntityId")
    stance: str
    claims: list[KnowledgeClaimRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class KnowledgeGraphRead(BaseModel):
    nodes: list[dict]
    edges: list[dict]


class KnowledgeSummaryRead(BaseModel):
    entities: int
    claims: int
    evidence: int
    relationships: int
    graph: KnowledgeGraphRead


class PropositionRead(BaseModel):
    id: UUID
    subject: str
    predicate: str
    object: str
    description: str
    context: dict | None
    provenance: dict | None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ScientificEvidenceRead(BaseModel):
    id: UUID
    paper_id: UUID | None = Field(serialization_alias="paperId")
    proposition_id: UUID | None = Field(default=None, serialization_alias="propositionId")
    evidence_type: str = Field(serialization_alias="evidenceType")
    extracted_text: str = Field(serialization_alias="extractedText")
    source_location: str = Field(serialization_alias="sourceLocation")
    source_span: dict | None = Field(serialization_alias="sourceSpan")
    polarity: str | None
    strength: float
    confidence: float
    extraction_method: str | None = Field(default=None, serialization_alias="extractionMethod")
    provenance: dict | None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class HypothesisRead(BaseModel):
    id: UUID
    proposition: PropositionRead | None
    statement: str
    description: str | None
    status: str
    confidence: float
    strength: float
    supporting_evidence_count: int = Field(serialization_alias="supportingEvidenceCount")
    contradictory_evidence_count: int = Field(serialization_alias="contradictoryEvidenceCount")
    uncertainty: dict | None
    provenance: dict | None
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ContradictionRead(BaseModel):
    id: UUID
    proposition: PropositionRead
    supporting_evidence: ScientificEvidenceRead = Field(serialization_alias="supportingEvidence")
    contradictory_evidence: ScientificEvidenceRead = Field(serialization_alias="contradictoryEvidence")
    contradiction_type: str = Field(serialization_alias="contradictionType")
    context: dict | None
    confidence: float
    provenance: dict | None
    created_at: datetime = Field(serialization_alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class KnowledgeGapRead(BaseModel):
    id: UUID
    description: str
    severity: str
    status: str
    hypothesis_id: UUID | None = Field(default=None, serialization_alias="hypothesisId")
    proposition_id: UUID | None = Field(default=None, serialization_alias="propositionId")
    evidence_count: int = Field(serialization_alias="evidenceCount")
    contradiction_count: int = Field(serialization_alias="contradictionCount")
    confidence: float
    rationale: str | None
    research_opportunity: str | None = Field(default=None, serialization_alias="researchOpportunity")
    related_entity_ids: list | None = Field(default=None, serialization_alias="relatedEntityIds")
    provenance: dict | None
    created_at: datetime = Field(serialization_alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ReasoningRead(BaseModel):
    id: UUID
    hypothesis_id: UUID = Field(serialization_alias="hypothesisId")
    reasoning_summary: str = Field(serialization_alias="reasoningSummary")
    rule_name: str = Field(serialization_alias="ruleName")
    strength: float
    confidence: float
    trace: dict
    created_at: datetime = Field(serialization_alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ReasoningSummaryRead(BaseModel):
    hypotheses: int
    contradictions: int
    knowledge_gaps: int = Field(serialization_alias="knowledgeGaps")
    traces: int
    items: list[ReasoningRead]

    model_config = ConfigDict(populate_by_name=True)


class InvestigationRunRead(BaseModel):
    id: UUID
    investigation_id: UUID = Field(serialization_alias="investigationId")
    parent_run_id: UUID | None = Field(default=None, serialization_alias="parentRunId")
    run_number: int = Field(serialization_alias="runNumber")
    status: str
    code_version: str = Field(serialization_alias="codeVersion")
    schema_version: str = Field(serialization_alias="schemaVersion")
    plan_hash: str | None = Field(default=None, serialization_alias="planHash")
    input_manifest: dict | None = Field(default=None, serialization_alias="inputManifest")
    provider_metadata: dict | None = Field(default=None, serialization_alias="providerMetadata")
    error_message: str | None = Field(default=None, serialization_alias="errorMessage")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    completed_at: datetime | None = Field(default=None, serialization_alias="completedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    snapshot_id: UUID | None = Field(default=None, serialization_alias="snapshotId")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class InvestigationSnapshotCreate(BaseModel):
    run_id: UUID | None = Field(default=None, alias="runId")

    model_config = ConfigDict(populate_by_name=True)


class ResearchSnapshotRead(BaseModel):
    id: UUID
    investigation_id: UUID = Field(serialization_alias="investigationId")
    run_id: UUID = Field(serialization_alias="runId")
    created_by_user_id: UUID | None = Field(default=None, serialization_alias="createdByUserId")
    snapshot_number: int = Field(serialization_alias="snapshotNumber")
    schema_version: str = Field(serialization_alias="schemaVersion")
    formula_version: str | None = Field(default=None, serialization_alias="formulaVersion")
    metta_digest: str | None = Field(default=None, serialization_alias="mettaDigest")
    manifest_digest: str = Field(serialization_alias="manifestDigest")
    manifest: dict
    created_at: datetime = Field(serialization_alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ResearchArtifactRead(BaseModel):
    id: UUID
    snapshot_id: UUID = Field(serialization_alias="snapshotId")
    artifact_type: str = Field(serialization_alias="artifactType")
    artifact_format: str = Field(serialization_alias="artifactFormat")
    status: str
    generator_version: str = Field(serialization_alias="generatorVersion")
    schema_version: str = Field(serialization_alias="schemaVersion")
    content_digest: str | None = Field(default=None, serialization_alias="contentDigest")
    manifest_digest: str = Field(serialization_alias="manifestDigest")
    metadata: dict | None = None
    created_at: datetime = Field(serialization_alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
