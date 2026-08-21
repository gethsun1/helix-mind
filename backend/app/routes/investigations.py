from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from redis.exceptions import RedisError
from sqlalchemy import select

from app.db import SessionLocal
from app.jobs import start_investigation
from app.models import Investigation, InvestigationEvent, InvestigationPaper, Paper, User
from app.queue import get_research_queue
from app.security import get_current_user
from app.schemas import InvestigationCreate, InvestigationCreated, InvestigationEventRead, InvestigationRead, PaperRead

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


@router.post("", response_model=InvestigationCreated, status_code=status.HTTP_202_ACCEPTED)
def create_investigation(payload: InvestigationCreate, user: User = Depends(get_current_user)) -> InvestigationCreated:
    session = SessionLocal()
    try:
        investigation = Investigation(owner_id=user.id, question=payload.question.strip())
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
def get_investigation(investigation_id: UUID, user: User = Depends(get_current_user)) -> InvestigationRead:
    session = SessionLocal()
    try:
        investigation = session.scalar(
            select(Investigation).where(Investigation.id == investigation_id, Investigation.owner_id == user.id)
        )
        if investigation is None:
            raise HTTPException(status_code=404, detail="Investigation not found.")
        return InvestigationRead(id=investigation.id, question=investigation.question, status=investigation.status)
    finally:
        session.close()


@router.get("/{investigation_id}/events", response_model=list[InvestigationEventRead])
def get_investigation_events(investigation_id: UUID, user: User = Depends(get_current_user)) -> list[InvestigationEventRead]:
    session = SessionLocal()
    try:
        if session.scalar(select(Investigation.id).where(Investigation.id == investigation_id, Investigation.owner_id == user.id)) is None:
            raise HTTPException(status_code=404, detail="Investigation not found.")
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


@router.get("/{investigation_id}/papers", response_model=list[PaperRead])
def get_investigation_papers(investigation_id: UUID, user: User = Depends(get_current_user)) -> list[PaperRead]:
    session = SessionLocal()
    try:
        if session.scalar(select(Investigation.id).where(Investigation.id == investigation_id, Investigation.owner_id == user.id)) is None:
            raise HTTPException(status_code=404, detail="Investigation not found.")
        papers = session.scalars(
            select(Paper)
            .join(InvestigationPaper, InvestigationPaper.paper_id == Paper.id)
            .where(InvestigationPaper.investigation_id == investigation_id)
            .order_by(Paper.created_at.asc())
        ).all()
        return [
            PaperRead(
                id=paper.id,
                source=paper.source,
                external_id=paper.external_id,
                title=paper.title,
                abstract=paper.abstract,
                authors=paper.authors,
                publication_date=paper.publication_date,
                doi=paper.doi,
                url=paper.url,
                metadata=paper.paper_metadata,
            )
            for paper in papers
        ]
    finally:
        session.close()


@router.get("", response_model=list[InvestigationRead])
def list_investigations(user: User = Depends(get_current_user)) -> list[InvestigationRead]:
    session = SessionLocal()
    try:
        investigations = session.scalars(
            select(Investigation)
            .where(Investigation.owner_id == user.id)
            .order_by(Investigation.updated_at.desc())
        ).all()
        return [
            InvestigationRead(id=item.id, question=item.question, status=item.status)
            for item in investigations
        ]
    finally:
        session.close()
