from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Investigation, InvestigationEvent, InvestigationRun, ResearchMemory, ResearchSnapshot, User
from app.security import get_current_user

router = APIRouter(prefix="/api/v1/investigations", tags=["research-memory"])
MEMORY_TYPES = {"HUMAN_CLINICAL_PRIORITY", "OFF_TARGET_CONSTRAINT"}


class MemoryCreate(BaseModel):
    memory_type: str
    decision_text: str = Field(min_length=8, max_length=1000)
    source_run_id: UUID | None = None
    source_snapshot_id: UUID | None = None


class MemoryRead(BaseModel):
    id: UUID
    investigation_id: UUID
    memory_type: str
    decision_text: str
    source_run_id: UUID | None
    source_snapshot_id: UUID | None
    active: bool
    deactivated_at: datetime | None
    metadata: dict | None
    created_at: datetime

    @classmethod
    def from_row(cls, row):
        return cls(id=row.id, investigation_id=row.investigation_id, memory_type=row.memory_type, decision_text=row.decision_text, source_run_id=row.source_run_id, source_snapshot_id=row.source_snapshot_id, active=row.active, deactivated_at=row.deactivated_at, metadata=row.audit_metadata, created_at=row.created_at)


def _scope(session, investigation_id, user):
    query = select(Investigation).where(Investigation.id == investigation_id)
    if user.role != "ADMIN":
        query = query.where(Investigation.owner_id == user.id)
    item = session.scalar(query)
    if item is None:
        raise HTTPException(404, "Investigation not found.")
    return item


@router.get("/{investigation_id}/memories", response_model=list[MemoryRead])
def list_memories(investigation_id: UUID, user: User = Depends(get_current_user)):
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        rows = session.scalars(select(ResearchMemory).where(ResearchMemory.investigation_id == investigation_id).order_by(ResearchMemory.created_at.desc()))
        return [MemoryRead.from_row(row) for row in rows]


@router.post("/{investigation_id}/memories", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
def create_memory(investigation_id: UUID, payload: MemoryCreate, user: User = Depends(get_current_user)):
    kind = payload.memory_type.strip().upper()
    if kind not in MEMORY_TYPES:
        raise HTTPException(422, "Choose a supported structured research memory type.")
    with SessionLocal() as session:
        investigation = _scope(session, investigation_id, user)
        run = session.scalar(select(InvestigationRun).where(InvestigationRun.id == payload.source_run_id, InvestigationRun.investigation_id == investigation_id)) if payload.source_run_id else None
        snapshot = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.id == payload.source_snapshot_id, ResearchSnapshot.investigation_id == investigation_id)) if payload.source_snapshot_id else None
        if payload.source_run_id and run is None:
            raise HTTPException(422, "Source run must belong to this investigation.")
        if payload.source_snapshot_id and snapshot is None:
            raise HTTPException(422, "Source snapshot must belong to this investigation.")
        metadata = {"created_by": str(user.id), "decision_origin": "explicit_user_save", "decision": payload.decision_text.strip()}
        row = ResearchMemory(owner_id=investigation.owner_id, investigation_id=investigation_id, memory_type=kind, decision_text=payload.decision_text.strip(), source_run_id=run.id if run else None, source_snapshot_id=snapshot.id if snapshot else None, audit_metadata=metadata)
        session.add(row)
        session.flush()
        session.add(InvestigationEvent(investigation_id=investigation_id, event_type="research_memory_saved", message="Researcher explicitly saved a persistent research decision.", event_metadata={"memory_id": str(row.id), "memory_type": kind, "source_run_id": str(run.id) if run else None, "source_snapshot_id": str(snapshot.id) if snapshot else None}))
        session.commit()
        session.refresh(row)
        return MemoryRead.from_row(row)


@router.post("/{investigation_id}/memories/{memory_id}/deactivate", response_model=MemoryRead)
def deactivate_memory(investigation_id: UUID, memory_id: UUID, user: User = Depends(get_current_user)):
    with SessionLocal() as session:
        investigation = _scope(session, investigation_id, user)
        query = select(ResearchMemory).where(ResearchMemory.id == memory_id, ResearchMemory.investigation_id == investigation.id)
        if user.role != "ADMIN":
            query = query.where(ResearchMemory.owner_id == user.id)
        row = session.scalar(query)
        if row is None:
            raise HTTPException(404, "Research memory not found.")
        if row.active:
            row.active = False
            row.deactivated_at = datetime.now(timezone.utc)
            session.add(InvestigationEvent(investigation_id=investigation_id, event_type="research_memory_deactivated", message="Research memory deactivated by its owner.", event_metadata={"memory_id": str(row.id), "actor_id": str(user.id)}))
            session.commit()
            session.refresh(row)
        return MemoryRead.from_row(row)
