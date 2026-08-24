from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.db import SessionLocal
from app.knowledge import investigation_graph
from app.models import Claim, ClaimEntity, ClaimEvidence, Entity, Evidence, Investigation, Relationship, RelationshipClaim, User
from app.schemas import KnowledgeClaimRead, KnowledgeEntityRead, KnowledgeEvidenceRead, KnowledgeGraphRead, KnowledgeRelationshipRead, KnowledgeSummaryRead
from app.security import get_current_user

router = APIRouter(prefix="/api/v1/investigations", tags=["knowledge"])


def _scope(session, investigation_id: UUID, user: User) -> Investigation:
    query = select(Investigation).where(Investigation.id == investigation_id)
    if user.role != "ADMIN":
        query = query.where(Investigation.owner_id == user.id)
    investigation = session.scalar(query)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return investigation


def _claim_read(session, claim: Claim) -> KnowledgeClaimRead:
    evidence = session.scalars(select(Evidence).join(ClaimEvidence, ClaimEvidence.evidence_id == Evidence.id).where(ClaimEvidence.claim_id == claim.id)).all()
    return KnowledgeClaimRead(id=claim.id, paper_id=claim.paper_id, claim_text=claim.claim_text, extraction_method=claim.extraction_method, extraction_confidence=float(claim.extraction_confidence) if claim.extraction_confidence is not None else None, evidence=[KnowledgeEvidenceRead.model_validate(item, from_attributes=True) for item in evidence])


@router.get("/{investigation_id}/knowledge", response_model=KnowledgeSummaryRead)
def knowledge_summary(investigation_id: UUID, q: str | None = None, limit: int = Query(default=200, ge=1, le=500), user: User = Depends(get_current_user)) -> KnowledgeSummaryRead:
    session = SessionLocal()
    try:
        _scope(session, investigation_id, user)
        graph = investigation_graph(session, investigation_id, query=q, limit=limit)
        entity_count = session.scalar(select(func.count(func.distinct(ClaimEntity.entity_id))).join(Claim, Claim.id == ClaimEntity.claim_id).where(Claim.investigation_id == investigation_id)) or 0
        claim_count = session.scalar(select(func.count()).select_from(Claim).where(Claim.investigation_id == investigation_id)) or 0
        evidence_count = session.scalar(select(func.count(func.distinct(ClaimEvidence.evidence_id))).join(Claim, Claim.id == ClaimEvidence.claim_id).where(Claim.investigation_id == investigation_id)) or 0
        relationship_count = session.scalar(select(func.count()).select_from(Relationship).where(Relationship.investigation_id == investigation_id)) or 0
        return KnowledgeSummaryRead(entities=entity_count, claims=claim_count, evidence=evidence_count, relationships=relationship_count, graph=graph)
    finally:
        session.close()


@router.get("/{investigation_id}/knowledge/graph", response_model=KnowledgeGraphRead)
def knowledge_graph(investigation_id: UUID, q: str | None = None, limit: int = Query(default=200, ge=1, le=500), user: User = Depends(get_current_user)) -> KnowledgeGraphRead:
    session = SessionLocal()
    try:
        _scope(session, investigation_id, user)
        return KnowledgeGraphRead(**investigation_graph(session, investigation_id, query=q, limit=limit))
    finally:
        session.close()


@router.get("/{investigation_id}/knowledge/entities", response_model=list[KnowledgeEntityRead])
def knowledge_entities(investigation_id: UUID, limit: int = Query(default=200, ge=1, le=500), user: User = Depends(get_current_user)) -> list[KnowledgeEntityRead]:
    session = SessionLocal()
    try:
        _scope(session, investigation_id, user)
        rows = session.scalars(select(Entity).join(ClaimEntity, ClaimEntity.entity_id == Entity.id).join(Claim, Claim.id == ClaimEntity.claim_id).where(Claim.investigation_id == investigation_id).distinct().limit(limit)).all()
        return [KnowledgeEntityRead.model_validate(item, from_attributes=True) for item in rows]
    finally:
        session.close()


@router.get("/{investigation_id}/knowledge/claims", response_model=list[KnowledgeClaimRead])
def knowledge_claims(investigation_id: UUID, limit: int = Query(default=200, ge=1, le=500), user: User = Depends(get_current_user)) -> list[KnowledgeClaimRead]:
    session = SessionLocal()
    try:
        _scope(session, investigation_id, user)
        rows = session.scalars(select(Claim).where(Claim.investigation_id == investigation_id).order_by(Claim.created_at.asc()).limit(limit)).all()
        return [_claim_read(session, item) for item in rows]
    finally:
        session.close()


@router.get("/{investigation_id}/knowledge/relationships", response_model=list[KnowledgeRelationshipRead])
def knowledge_relationships(investigation_id: UUID, limit: int = Query(default=200, ge=1, le=500), user: User = Depends(get_current_user)) -> list[KnowledgeRelationshipRead]:
    session = SessionLocal()
    try:
        _scope(session, investigation_id, user)
        rows = session.scalars(select(Relationship).where(Relationship.investigation_id == investigation_id).limit(limit)).all()
        result = []
        for relationship in rows:
            claims = session.scalars(select(Claim).join(RelationshipClaim, RelationshipClaim.claim_id == Claim.id).where(RelationshipClaim.relationship_id == relationship.id)).all()
            result.append(KnowledgeRelationshipRead(id=relationship.id, subject_entity_id=relationship.subject_entity_id, predicate=relationship.predicate, object_entity_id=relationship.object_entity_id, stance=relationship.stance, claims=[_claim_read(session, claim) for claim in claims]))
        return result
    finally:
        session.close()
