from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class InvestigationCreate(BaseModel):
    question: str = Field(min_length=10, max_length=5_000)


class InvestigationCreated(BaseModel):
    id: UUID
    status: str


class InvestigationEventRead(BaseModel):
    event_type: str
    message: str
    metadata: dict | None
    timestamp: datetime


class InvestigationRead(BaseModel):
    id: UUID
    question: str
    status: str


class UserRead(BaseModel):
    id: UUID
    email: str
    name: str | None
    image: str | None
    role: str
    organization: str | None
    research_focus: str | None


class OAuthUserSync(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    name: str | None = Field(default=None, max_length=255)
    image: str | None = Field(default=None, max_length=2_000)
    provider_account_id: str | None = Field(default=None, max_length=255)


class PaperRead(BaseModel):
    id: UUID
    source: str
    external_id: str
    title: str
    abstract: str | None
    authors: list | None
    publication_date: date | None
    doi: str | None
    url: str | None
    metadata: dict | None
