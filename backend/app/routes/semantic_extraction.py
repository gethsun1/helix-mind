from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Investigation, InvestigationRun, ResearchSnapshot, SemanticExtraction, User
from app.routes.literature_intelligence import _scope
from app.security import get_current_user
from app.semantic_extraction import execute_semantic_extraction, extraction_read

router = APIRouter(prefix="/api/v1/investigations", tags=["semantic extraction"])


class SemanticExtractionCreate(BaseModel):
    source_run_id: UUID


@router.get("/{investigation_id}/literature/semantic-extractions")
def list_semantic_extractions(investigation_id: UUID, limit: int = Query(default=500, ge=1, le=2000),
                              user: User = Depends(get_current_user)) -> dict:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        rows = session.scalars(select(SemanticExtraction).where(
            SemanticExtraction.investigation_id == investigation_id
        ).order_by(SemanticExtraction.created_at.desc(), SemanticExtraction.evidence_id.asc(),
                   SemanticExtraction.content_hash.asc()).limit(limit)).all()
        return {"investigationId": str(investigation_id), "extractions": [extraction_read(row) for row in rows]}


@router.get("/{investigation_id}/literature/semantic-extractions/{extraction_id}")
def get_semantic_extraction(investigation_id: UUID, extraction_id: UUID,
                            user: User = Depends(get_current_user)) -> dict:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        row = session.scalar(select(SemanticExtraction).where(
            SemanticExtraction.id == extraction_id,
            SemanticExtraction.investigation_id == investigation_id))
        if row is None:
            raise HTTPException(status_code=404, detail="Semantic extraction not found.")
        return extraction_read(row)


@router.post("/{investigation_id}/literature/semantic-extractions", status_code=200)
def create_semantic_extractions(investigation_id: UUID, payload: SemanticExtractionCreate,
                                user: User = Depends(get_current_user)) -> dict:
    with SessionLocal() as session:
        investigation = _scope(session, investigation_id, user)
        source_run = session.scalar(select(InvestigationRun).where(
            InvestigationRun.id == payload.source_run_id,
            InvestigationRun.investigation_id == investigation_id))
        if source_run is None:
            raise HTTPException(status_code=404, detail="Source run not found in this investigation.")
        if source_run.status != "COMPLETED":
            raise HTTPException(status_code=409, detail="Semantic extraction requires a completed source run.")
        if session.scalar(select(ResearchSnapshot.id).where(
            ResearchSnapshot.run_id == source_run.id, ResearchSnapshot.investigation_id == investigation_id)) is None:
            raise HTTPException(status_code=409, detail="Semantic extraction requires an immutable source-run snapshot.")
        try:
            return execute_semantic_extraction(session, investigation, source_run)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            # Provider/parse failures must not expose request data, credentials, or provider response bodies.
            raise HTTPException(status_code=502, detail="Semantic extraction provider failed; no candidate was promoted.") from error
