from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from redis.exceptions import RedisError
from sqlalchemy import select

from app.db import SessionLocal
from app.jobs import start_investigation
from app.models import Investigation, InvestigationEvent, InvestigationRun, User
from app.queue import get_research_queue
from app.schemas import (
    InvestigationCancelResponse,
    InvestigationCreate,
    InvestigationCreated,
    InvestigationEventRead,
    InvestigationRead,
)
from app.security import get_current_user

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


def _event_read(event: InvestigationEvent) -> InvestigationEventRead:
    return InvestigationEventRead(
        id=event.id,
        event_type=event.event_type,
        message=event.message,
        metadata=event.event_metadata,
        timestamp=event.timestamp,
    )


def _owner_scope(investigation_id: UUID, user: User):
    query = select(Investigation).where(Investigation.id == investigation_id)
    if user.role != "ADMIN":
        query = query.where(Investigation.owner_id == user.id)
    return query


def _read_investigation(session, investigation: Investigation) -> InvestigationRead:
    events = session.scalars(
        select(InvestigationEvent)
        .where(InvestigationEvent.investigation_id == investigation.id)
        .order_by(InvestigationEvent.timestamp.asc())
    ).all()
    return InvestigationRead(
        id=investigation.id,
        owner_id=investigation.owner_id,
        title=investigation.title,
        research_question=investigation.question,
        domain=investigation.domain,
        status=investigation.status,
        created_at=investigation.created_at,
        updated_at=investigation.updated_at,
        started_at=investigation.started_at,
        completed_at=investigation.completed_at,
        error_message=investigation.error_message,
        research_plan=investigation.research_plan,
        events=[_event_read(event) for event in events],
    )


@router.post("", response_model=InvestigationCreated, status_code=status.HTTP_202_ACCEPTED)
def create_investigation(payload: InvestigationCreate, user: User = Depends(get_current_user)) -> InvestigationCreated:
    session = SessionLocal()
    try:
        investigation = Investigation(
            owner_id=user.id,
            title=payload.title,
            question=payload.research_question,
            domain=payload.domain,
            status="QUEUED",
        )
        session.add(investigation)
        session.flush()
        session.add(
            InvestigationEvent(
                investigation_id=investigation.id,
                event_type="investigation_created",
                message="Investigation created and awaiting the HelixMind research worker.",
                event_metadata={"owner_id": str(user.id), "domain": payload.domain},
            )
        )
        session.commit()
        session.refresh(investigation)
        investigation_id = investigation.id
        created_at = investigation.created_at
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    try:
        get_research_queue().enqueue(start_investigation, str(investigation_id))
    except RedisError as error:
        with SessionLocal() as failed_session:
            failed = failed_session.get(Investigation, investigation_id)
            if failed is not None:
                failed.status = "FAILED"
                failed.error_message = "HelixMind research queue is unavailable."
                failed_session.add(
                    InvestigationEvent(
                        investigation_id=investigation_id,
                        event_type="investigation_failed",
                        message="The research queue was unavailable; the investigation was not started.",
                        event_metadata={"category": "SYSTEM_ERROR"},
                    )
                )
                failed_session.commit()
        raise HTTPException(status_code=503, detail="HelixMind research queue is unavailable.") from error

    return InvestigationCreated(id=investigation_id, status="QUEUED", created_at=created_at)


@router.get("", response_model=list[InvestigationRead])
def list_investigations(user: User = Depends(get_current_user)) -> list[InvestigationRead]:
    session = SessionLocal()
    try:
        query = select(Investigation).order_by(Investigation.updated_at.desc())
        if user.role != "ADMIN":
            query = query.where(Investigation.owner_id == user.id)
        return [_read_investigation(session, item) for item in session.scalars(query).all()]
    finally:
        session.close()


@router.get("/{investigation_id}", response_model=InvestigationRead)
def get_investigation(investigation_id: UUID, user: User = Depends(get_current_user)) -> InvestigationRead:
    session = SessionLocal()
    try:
        investigation = session.scalar(_owner_scope(investigation_id, user))
        if investigation is None:
            raise HTTPException(status_code=404, detail="Investigation not found.")
        return _read_investigation(session, investigation)
    finally:
        session.close()


@router.post("/{investigation_id}/cancel", response_model=InvestigationCancelResponse)
def cancel_investigation(investigation_id: UUID, user: User = Depends(get_current_user)) -> InvestigationCancelResponse:
    session = SessionLocal()
    try:
        investigation = session.scalar(_owner_scope(investigation_id, user))
        if investigation is None:
            raise HTTPException(status_code=404, detail="Investigation not found.")
        if investigation.status.upper() != "QUEUED":
            raise HTTPException(status_code=409, detail="Only queued investigations can be cancelled.")
        investigation.status = "CANCELLED"
        investigation.updated_at = datetime.now(timezone.utc)
        queued_run = session.scalar(select(InvestigationRun).where(InvestigationRun.investigation_id == investigation.id, InvestigationRun.status == "QUEUED").order_by(InvestigationRun.run_number.desc()).limit(1))
        if queued_run is not None:
            queued_run.status = "CANCELLED"
            queued_run.completed_at = datetime.now(timezone.utc)
        session.add(
            InvestigationEvent(
                investigation_id=investigation.id,
                event_type="investigation_cancelled",
                message="Investigation cancelled before worker processing began.",
                event_metadata={"actor": "owner" if user.role != "ADMIN" else "admin"},
            )
        )
        session.commit()
        return InvestigationCancelResponse(id=investigation.id, status=investigation.status)
    finally:
        session.close()


@router.get("/{investigation_id}/events", response_model=list[InvestigationEventRead])
def get_investigation_events(investigation_id: UUID, user: User = Depends(get_current_user)) -> list[InvestigationEventRead]:
    session = SessionLocal()
    try:
        if session.scalar(_owner_scope(investigation_id, user)) is None:
            raise HTTPException(status_code=404, detail="Investigation not found.")
        events = session.scalars(
            select(InvestigationEvent)
            .where(InvestigationEvent.investigation_id == investigation_id)
            .order_by(InvestigationEvent.timestamp.asc())
        ).all()
        return [_event_read(event) for event in events]
    finally:
        session.close()
