from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Claim, ClaimEvidence, Contradiction, Evidence, Hypothesis, Inference, Investigation, KnowledgeGap, Paper, Proposition, User
from app.schemas import ContradictionRead, HypothesisRead, KnowledgeGapRead, PropositionRead, ReasoningRead, ReasoningSummaryRead, ScientificEvidenceRead
from app.security import get_current_user


router = APIRouter(prefix="/api/v1/investigations", tags=["scientific-reasoning"])


def _scope(session, investigation_id: UUID, user: User) -> Investigation:
    query = select(Investigation).where(Investigation.id == investigation_id)
    if user.role != "ADMIN":
        query = query.where(Investigation.owner_id == user.id)
    investigation = session.scalar(query)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return investigation


def _proposition(session, proposition_id: UUID | None) -> PropositionRead | None:
    if proposition_id is None:
        return None
    item = session.get(Proposition, proposition_id)
    return PropositionRead.model_validate(item, from_attributes=True) if item else None


def _evidence(item: Evidence) -> ScientificEvidenceRead:
    return ScientificEvidenceRead(id=item.id, paper_id=item.paper_id, proposition_id=item.proposition_id, evidence_type=item.evidence_type, extracted_text=item.extracted_text, source_location=item.source_location, source_span=item.source_span, polarity=item.polarity, strength=float(item.strength or 0), confidence=float(item.confidence or 0), extraction_method=item.extraction_method, provenance={"paper_id": str(item.paper_id) if item.paper_id else None, "source_location": item.source_location, "source_span": item.source_span})


def _reasoning(item: Inference) -> ReasoningRead:
    return ReasoningRead(id=item.id, hypothesis_id=item.hypothesis_id, reasoning_summary=item.reasoning_summary, rule_name=item.rule_name, strength=float(item.strength or 0), confidence=float(item.confidence or 0), trace=item.inference_metadata or {}, created_at=item.created_at)


@router.get("/{investigation_id}/evidence", response_model=list[ScientificEvidenceRead])
def investigation_evidence(investigation_id: UUID, limit: int = Query(default=500, ge=1, le=2_000), polarity: str | None = Query(default=None, max_length=24), paper_id: UUID | None = Query(default=None, alias="paperId"), paper_source: str | None = Query(default=None, alias="paperSource", max_length=32), proposition_id: UUID | None = Query(default=None, alias="propositionId"), min_confidence: float | None = Query(default=None, alias="minConfidence", ge=0, le=1), max_confidence: float | None = Query(default=None, alias="maxConfidence", ge=0, le=1), provenance_only: bool = Query(default=False, alias="provenanceOnly"), user: User = Depends(get_current_user)) -> list[ScientificEvidenceRead]:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        query = select(Evidence).where(Evidence.investigation_id == investigation_id)
        if polarity:
            query = query.where(Evidence.polarity == polarity.strip().upper())
        if paper_id:
            query = query.where(Evidence.paper_id == paper_id)
        if paper_source:
            query = query.join(Paper, Paper.id == Evidence.paper_id).where(Paper.source == paper_source.strip().upper())
        if proposition_id:
            query = query.where(Evidence.proposition_id == proposition_id)
        if min_confidence is not None:
            query = query.where(Evidence.confidence >= min_confidence)
        if max_confidence is not None:
            query = query.where(Evidence.confidence <= max_confidence)
        if provenance_only:
            query = query.where(Evidence.paper_id.is_not(None), Evidence.source_span.is_not(None), Evidence.source_location.is_not(None))
        rows = session.scalars(query.order_by(Evidence.extraction_timestamp.asc()).limit(limit)).all()
        return [_evidence(item) for item in rows]


@router.get("/{investigation_id}/hypotheses", response_model=list[HypothesisRead])
def investigation_hypotheses(investigation_id: UUID, limit: int = Query(default=200, ge=1, le=500), user: User = Depends(get_current_user)) -> list[HypothesisRead]:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        rows = session.scalars(select(Hypothesis).where(Hypothesis.investigation_id == investigation_id).order_by(Hypothesis.updated_at.desc()).limit(limit)).all()
        result = []
        for item in rows:
            evidence = session.scalars(select(Evidence).where(Evidence.investigation_id == investigation_id, Evidence.proposition_id == item.proposition_id).order_by(Evidence.extraction_timestamp.asc())).all() if item.proposition_id else []
            result.append(HypothesisRead(id=item.id, proposition=_proposition(session, item.proposition_id), statement=item.statement, description=item.description, status=item.status, confidence=float(item.confidence or 0), strength=float(item.strength or 0), supporting_evidence_count=item.supporting_evidence_count, contradictory_evidence_count=item.contradictory_evidence_count, uncertainty=item.uncertainty, provenance=item.provenance, supporting_evidence=[_evidence(value) for value in evidence if value.polarity == "SUPPORTS"], contradictory_evidence=[_evidence(value) for value in evidence if value.polarity == "CONTRADICTS"], created_at=item.created_at, updated_at=item.updated_at))
        return result


@router.get("/{investigation_id}/contradictions", response_model=list[ContradictionRead])
def investigation_contradictions(investigation_id: UUID, limit: int = Query(default=200, ge=1, le=500), user: User = Depends(get_current_user)) -> list[ContradictionRead]:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        rows = session.scalars(select(Contradiction).where(Contradiction.investigation_id == investigation_id).order_by(Contradiction.created_at.asc()).limit(limit)).all()
        result = []
        for item in rows:
            proposition = _proposition(session, item.proposition_id)
            supporting = session.get(Evidence, item.supporting_evidence_id)
            contradictory = session.get(Evidence, item.contradictory_evidence_id)
            if proposition and supporting and contradictory:
                result.append(ContradictionRead(id=item.id, proposition=proposition, supporting_evidence=_evidence(supporting), contradictory_evidence=_evidence(contradictory), contradiction_type=item.contradiction_type, context=item.context, confidence=float(item.confidence or 0), provenance=item.provenance, created_at=item.created_at))
        return result


@router.get("/{investigation_id}/knowledge-gaps", response_model=list[KnowledgeGapRead])
def investigation_knowledge_gaps(investigation_id: UUID, limit: int = Query(default=200, ge=1, le=500), user: User = Depends(get_current_user)) -> list[KnowledgeGapRead]:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        rows = session.scalars(select(KnowledgeGap).where(KnowledgeGap.investigation_id == investigation_id).order_by(KnowledgeGap.created_at.asc()).limit(limit)).all()
        return [KnowledgeGapRead.model_validate(item, from_attributes=True) for item in rows]


def _reasoning_rows(session, investigation_id: UUID, limit: int) -> list[ReasoningRead]:
    rows = session.scalars(select(Inference).join(Hypothesis, Hypothesis.id == Inference.hypothesis_id).where(Hypothesis.investigation_id == investigation_id).order_by(Inference.created_at.desc()).limit(limit)).all()
    return [_reasoning(item) for item in rows]


@router.get("/{investigation_id}/reasoning", response_model=ReasoningSummaryRead)
def investigation_reasoning(investigation_id: UUID, limit: int = Query(default=200, ge=1, le=500), user: User = Depends(get_current_user)) -> ReasoningSummaryRead:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        items = _reasoning_rows(session, investigation_id, limit)
        return ReasoningSummaryRead(hypotheses=session.scalar(select(func.count()).select_from(Hypothesis).where(Hypothesis.investigation_id == investigation_id)) or 0, contradictions=session.scalar(select(func.count()).select_from(Contradiction).where(Contradiction.investigation_id == investigation_id)) or 0, knowledge_gaps=session.scalar(select(func.count()).select_from(KnowledgeGap).where(KnowledgeGap.investigation_id == investigation_id, KnowledgeGap.status == "open")) or 0, traces=len(items), items=items)


@router.get("/{investigation_id}/reasoning/trace", response_model=list[ReasoningRead])
def investigation_reasoning_trace(investigation_id: UUID, limit: int = Query(default=200, ge=1, le=500), user: User = Depends(get_current_user)) -> list[ReasoningRead]:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        return _reasoning_rows(session, investigation_id, limit)
