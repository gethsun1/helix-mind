from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from redis.exceptions import RedisError
from sqlalchemy import select

from app.db import SessionLocal
from app.jobs import start_investigation
from app.models import Investigation, InvestigationEvent
from app.queue import get_research_queue
from app.schemas import InvestigationCreate, InvestigationCreated, InvestigationEventRead, InvestigationRead

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


@router.post("", response_model=InvestigationCreated, status_code=status.HTTP_202_ACCEPTED)
def create_investigation(payload: InvestigationCreate) -> InvestigationCreated:
    session = SessionLocal()
    try:
        investigation = Investigation(question=payload.question.strip())
        session.add(investigation)
        session.flush()
        investigation_id = investigation.id
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    try:
        get_research_queue().enqueue(start_investigation, str(investigation_id))
    except RedisError as error:
        raise HTTPException(status_code=503, detail="HelixMind research queue is unavailable.") from error

    return InvestigationCreated(id=investigation_id, status="queued")


@router.get("/{investigation_id}", response_model=InvestigationRead)
def get_investigation(investigation_id: UUID) -> InvestigationRead:
    session = SessionLocal()
    try:
        investigation = session.get(Investigation, investigation_id)
        if investigation is None:
            raise HTTPException(status_code=404, detail="Investigation not found.")
        return InvestigationRead(id=investigation.id, question=investigation.question, status=investigation.status)
    finally:
        session.close()


@router.get("/{investigation_id}/events", response_model=list[InvestigationEventRead])
def get_investigation_events(investigation_id: UUID) -> list[InvestigationEventRead]:
    session = SessionLocal()
    try:
        events = session.scalars(
            select(InvestigationEvent)
            .where(InvestigationEvent.investigation_id == investigation_id)
            .order_by(InvestigationEvent.timestamp.asc())
        ).all()
        return [
            InvestigationEventRead(
                event_type=event.event_type,
                message=event.message,
                metadata=event.event_metadata,
                timestamp=event.timestamp,
            )
            for event in events
        ]
    finally:
        session.close()
