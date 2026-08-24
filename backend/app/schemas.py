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
