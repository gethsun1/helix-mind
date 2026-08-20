from datetime import datetime
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
