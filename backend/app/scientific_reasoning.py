"""Deterministic Phase 3E aggregation over source-linked knowledge.

This module never asks a language model to decide whether a hypothesis is true.
It aggregates explicit evidence polarity, source independence, extraction
confidence, and provenance completeness, then persists an inspectable trace.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.knowledge_metta import render_investigation_metta, validate_metta_text
from app.models import (
    Claim,
    ClaimEvidence,
    Contradiction,
    Entity,
    Evidence,
    Hypothesis,
    Inference,
    Investigation,
    InvestigationEvent,
    KnowledgeGap,
    Proposition,
    Relationship,
    RelationshipClaim,
)


SUPPORTS = "SUPPORTS"
CONTRADICTS = "CONTRADICTS"
NEUTRAL = "NEUTRAL"
UNCERTAIN = "UNCERTAIN"
POLARITIES = {SUPPORTS, CONTRADICTS, NEUTRAL, UNCERTAIN}


@dataclass(frozen=True)
class EvidenceAggregate:
    supporting: list[Evidence]
    contradictory: list[Evidence]
    neutral: list[Evidence]
    uncertain: list[Evidence]
    confidence: float
    uncertainty: dict[str, Any]


def clamp(value: float) -> float:
    return max(0.0, min(1.0, round(value, 3)))


def normalize_proposition_part(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def proposition_key(investigation_id: object, subject: str, predicate: str, object_name: str) -> str:
    raw = "|".join(
        [
            str(investigation_id),
            normalize_proposition_part(subject),
            normalize_proposition_part(predicate),
            normalize_proposition_part(object_name),
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def evidence_polarity(text: str) -> str:
    """Classify only explicit linguistic cues; absence of a cue is support."""
    value = text.lower()
    if re.search(r"\b(inconclusive|unclear|uncertain|mixed results?|may not|might not|could not)\b", value):
        return UNCERTAIN
    if re.search(r"\b(no significant|not significantly|did not|does not|do not|failed to|not associated|no evidence|without)\b", value):
        return CONTRADICTS
    if re.search(r"\b(neutral|unrelated|no difference)\b", value):
        return NEUTRAL
    return SUPPORTS


def evidence_weight(evidence: Evidence) -> float:
    """Use extraction signals, not a claim of methodological study quality."""
    strength = float(evidence.strength or 0)
    confidence = float(evidence.confidence or 0)
    return clamp(strength * confidence)


def aggregate_evidence(evidence: Iterable[Evidence]) -> EvidenceAggregate:
    items = list(evidence)
    supporting = [item for item in items if item.polarity == SUPPORTS]
    contradictory = [item for item in items if item.polarity == CONTRADICTS]
    neutral = [item for item in items if item.polarity == NEUTRAL]
    uncertain = [item for item in items if item.polarity == UNCERTAIN or item.polarity not in POLARITIES]
    support_signal = sum(evidence_weight(item) for item in supporting)
    contradiction_signal = sum(evidence_weight(item) for item in contradictory)
    total_signal = support_signal + contradiction_signal
    balance = support_signal / total_signal if total_signal else 0.0
    supporting_sources = len({str(item.paper_id) for item in supporting if item.paper_id})
    total_sources = len({str(item.paper_id) for item in items if item.paper_id})
    independence = min(supporting_sources, 3) / 3
    source_coverage = min(total_sources, 3) / 3
    assessed = [float(item.confidence or 0) for item in items]
    extraction_confidence = sum(assessed) / len(assessed) if assessed else 0.0
    provenance = sum(bool(item.paper_id and item.source_span and item.source_location) for item in items) / len(items) if items else 0.0
    # Formula: 45% weighted polarity balance, 25% independent support coverage,
    # 20% extraction confidence, 10% complete paper/span provenance. This is
    # HelixMind evidence confidence, not probability that a hypothesis is true.
    quality = sum(evidence_weight(item) for item in supporting + contradictory) / len(supporting + contradictory) if supporting or contradictory else 0.0
    confidence = clamp(0.45 * balance * quality * (0.5 + 0.5 * independence) + 0.25 * independence + 0.20 * extraction_confidence + 0.10 * provenance)
    uncertainty = {
        "neutral_evidence": len(neutral),
        "uncertain_evidence": len(uncertain),
        "supporting_sources": supporting_sources,
        "total_sources": total_sources,
        "contradiction_signal": round(contradiction_signal, 3),
        "formula": "0.45*polarity_balance*quality*(0.5+0.5*independent_support/3)+0.25*independent_support/3+0.20*mean_extraction_confidence+0.10*provenance_completeness",
        "semantics": "HelixMind evidence confidence; not scientific or clinical certainty",
    }
    return EvidenceAggregate(supporting, contradictory, neutral, uncertain, confidence, uncertainty)


def hypothesis_status(aggregate: EvidenceAggregate) -> str:
    if aggregate.supporting and aggregate.contradictory:
        return "CONTESTED"
    if aggregate.supporting and len({str(item.paper_id) for item in aggregate.supporting if item.paper_id}) >= 2 and aggregate.confidence >= 0.55:
        return "SUPPORTED"
    if aggregate.supporting:
        return "WEAK"
    return "UNRESOLVED"


def contradiction_type(supporting: Evidence, contradictory: Evidence) -> str:
    if supporting.source_span and contradictory.source_span:
        return "DIRECT"
    if supporting.section and contradictory.section and supporting.section != contradictory.section:
        return "CONTEXTUAL"
    return "INSUFFICIENT_EVIDENCE"


def transitive_support(edges: Iterable[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Small deterministic PLN-style transitive support rule for unit/integration use."""
    values = set(edges)
    derived: set[tuple[str, str, str]] = set()
    for source, predicate, middle in values:
        if predicate != SUPPORTS:
            continue
        for candidate, candidate_predicate, target in values:
            if candidate_predicate == SUPPORTS and candidate == middle:
                derived.add((source, SUPPORTS, target))
    return sorted(derived)


def _event(session: Session, investigation_id: object, event_type: str, message: str, metadata: dict[str, Any]) -> None:
    session.add(InvestigationEvent(investigation_id=investigation_id, event_type=event_type, message=message, event_metadata=metadata, timestamp=datetime.now(timezone.utc)))


def _proposition_description(proposition: Proposition) -> str:
    return f"{proposition.subject} {proposition.predicate.lower().replace('_', ' ')} {proposition.object}."


def _relationship_ids(session: Session, proposition: Proposition) -> list[str]:
    subject = normalize_proposition_part(proposition.subject)
    object_name = normalize_proposition_part(proposition.object)
    rows = session.scalars(select(Relationship).where(Relationship.investigation_id == proposition.investigation_id, Relationship.predicate == proposition.predicate)).all()
    return [str(row.id) for row in rows if str(row.subject_entity_id) == subject or str(row.object_entity_id) == object_name]


def run_scientific_reasoning(session: Session, investigation: Investigation) -> dict[str, int | float | str]:
    """Aggregate all structured evidence for one investigation idempotently."""
    started = datetime.now(timezone.utc)
    _event(session, investigation.id, "reasoning_started", "Deterministic evidence reasoning started.", {"engine": "HelixMindEvidenceReasoner", "formula_version": "3E-1"})
    session.commit()

    propositions = session.scalars(select(Proposition).where(Proposition.investigation_id == investigation.id).order_by(Proposition.created_at.asc())).all()
    evidence_rows = session.scalars(select(Evidence).where(Evidence.investigation_id == investigation.id)).all()
    by_proposition: dict[object, list[Evidence]] = {}
    for item in evidence_rows:
        by_proposition.setdefault(item.proposition_id, []).append(item)

    contradiction_count = 0
    gap_count = 0
    hypothesis_count = 0
    trace_count = 0
    for proposition in propositions:
        items = by_proposition.get(proposition.id, [])
        aggregate = aggregate_evidence(items)
        hypothesis = session.scalar(select(Hypothesis).where(Hypothesis.investigation_id == investigation.id, Hypothesis.proposition_id == proposition.id))
        if hypothesis is None:
            hypothesis = Hypothesis(investigation_id=investigation.id, proposition_id=proposition.id, statement=_proposition_description(proposition), description=proposition.description, strength=Decimal("0.600"), confidence=Decimal(str(aggregate.confidence)), status=hypothesis_status(aggregate), supporting_evidence_count=len(aggregate.supporting), contradictory_evidence_count=len(aggregate.contradictory), uncertainty=aggregate.uncertainty, provenance=proposition.provenance)
            session.add(hypothesis)
            session.flush()
            hypothesis_count += 1
            _event(session, investigation.id, "hypothesis_created", "A provisional hypothesis was created from a structured proposition.", {"hypothesis_id": str(hypothesis.id), "proposition_id": str(proposition.id), "source": "literature"})
        else:
            hypothesis.statement = _proposition_description(proposition)
            hypothesis.description = proposition.description
            hypothesis.confidence = Decimal(str(aggregate.confidence))
            hypothesis.status = hypothesis_status(aggregate)
            hypothesis.supporting_evidence_count = len(aggregate.supporting)
            hypothesis.contradictory_evidence_count = len(aggregate.contradictory)
            hypothesis.uncertainty = aggregate.uncertainty
            hypothesis.provenance = proposition.provenance
            hypothesis.updated_at = datetime.now(timezone.utc)

        for supporting in aggregate.supporting:
            for contradictory in aggregate.contradictory:
                kind = contradiction_type(supporting, contradictory)
                contradiction = session.scalar(select(Contradiction).where(Contradiction.investigation_id == investigation.id, Contradiction.proposition_id == proposition.id, Contradiction.supporting_evidence_id == supporting.id, Contradiction.contradictory_evidence_id == contradictory.id))
                if contradiction is None:
                    contradiction = Contradiction(investigation_id=investigation.id, proposition_id=proposition.id, supporting_evidence_id=supporting.id, contradictory_evidence_id=contradictory.id, contradiction_type=kind, context={"same_structured_proposition": True}, confidence=Decimal(str(min(float(supporting.confidence or 0), float(contradictory.confidence or 0)))), provenance={"supporting_paper_id": str(supporting.paper_id) if supporting.paper_id else None, "contradictory_paper_id": str(contradictory.paper_id) if contradictory.paper_id else None})
                    session.add(contradiction)
                    session.flush()
                    contradiction_count += 1
                    _event(session, investigation.id, "contradiction_detected", "Opposing evidence was found for the same structured proposition.", {"contradiction_id": str(contradiction.id), "proposition_id": str(proposition.id), "type": kind})

        result = "Evidence is supportive but contested." if aggregate.supporting and aggregate.contradictory else ("Available evidence is supportive." if aggregate.supporting else "No supporting evidence was identified for this proposition.")
        trace = {
            "question": investigation.question,
            "starting_proposition": {"id": str(proposition.id), "subject": proposition.subject, "predicate": proposition.predicate, "object": proposition.object},
            "evidence_considered": [str(item.id) for item in items],
            "supporting_evidence": [str(item.id) for item in aggregate.supporting],
            "contradictory_evidence": [str(item.id) for item in aggregate.contradictory],
            "neutral_evidence": [str(item.id) for item in aggregate.neutral],
            "uncertain_evidence": [str(item.id) for item in aggregate.uncertain],
            "relationships_applied": _relationship_ids(session, proposition),
            "inference_rule": "direct_evidence_balance",
            "result": result,
            "confidence": aggregate.confidence,
            "uncertainty": aggregate.uncertainty,
            "safety": "Research evidence assessment; not clinical certainty or treatment advice.",
        }
        inference = session.scalar(select(Inference).where(Inference.hypothesis_id == hypothesis.id))
        if inference is None:
            inference = Inference(hypothesis_id=hypothesis.id, reasoning_summary=result, strength=Decimal("0.600"), confidence=Decimal(str(aggregate.confidence)), rule_name="direct_evidence_balance", inference_metadata=trace)
            session.add(inference)
        else:
            inference.reasoning_summary = result
            inference.confidence = Decimal(str(aggregate.confidence))
            inference.inference_metadata = trace
            inference.rule_name = "direct_evidence_balance"
        trace_count += 1

        gap = session.scalar(select(KnowledgeGap).where(KnowledgeGap.investigation_id == investigation.id, KnowledgeGap.proposition_id == proposition.id, KnowledgeGap.status == "open"))
        needs_gap = not aggregate.supporting or aggregate.confidence < 0.55 or len(aggregate.contradictory) >= len(aggregate.supporting)
        if needs_gap:
            description = f"Insufficient or conflicting evidence for {proposition.subject} {proposition.predicate.lower().replace('_', ' ')} {proposition.object}."
            opportunity = f"Potential research opportunity: further studies could clarify {proposition.subject} {proposition.predicate.lower().replace('_', ' ')} {proposition.object}."
            severity = "HIGH" if not aggregate.supporting or aggregate.confidence < 0.35 else "MEDIUM"
            if gap is None:
                gap = KnowledgeGap(investigation_id=investigation.id, hypothesis_id=hypothesis.id, proposition_id=proposition.id, description=description, severity=severity, status="open", evidence_count=len(items), contradiction_count=len(aggregate.contradictory), confidence=Decimal(str(aggregate.confidence)), rationale="The deterministic evidence balance did not meet the configured support threshold.", research_opportunity=opportunity, related_entity_ids=[], provenance=proposition.provenance)
                session.add(gap)
                session.flush()
                gap_count += 1
                _event(session, investigation.id, "knowledge_gap_detected", "A knowledge gap was derived from evidence balance.", {"knowledge_gap_id": str(gap.id), "proposition_id": str(proposition.id), "severity": severity})
            else:
                gap.evidence_count = len(items)
                gap.contradiction_count = len(aggregate.contradictory)
                gap.confidence = Decimal(str(aggregate.confidence))
        elif gap is not None:
            gap.status = "resolved"

    if not propositions and evidence_rows:
        gap = KnowledgeGap(investigation_id=investigation.id, description="Retrieved evidence does not yet contain an explicit structured proposition.", severity="HIGH", status="open", evidence_count=len(evidence_rows), contradiction_count=0, confidence=Decimal("0"), rationale="The source-linked claims require an explicit subject-predicate-object relationship before hypothesis aggregation.", research_opportunity="Potential research opportunity: extract and validate structured relationships from the retrieved source text.", provenance={"evidence_ids": [str(item.id) for item in evidence_rows]})
        session.add(gap)
        gap_count += 1
        _event(session, investigation.id, "knowledge_gap_detected", "A structured proposition was missing from retrieved evidence.", {"severity": "HIGH", "evidence_count": len(evidence_rows)})

    session.flush()
    metta_text = render_investigation_metta(session, investigation.id)
    validate_metta_text(metta_text)
    _event(session, investigation.id, "reasoning_completed", "Deterministic evidence reasoning completed and MeTTa representation validated.", {"hypothesis_count": len(propositions), "contradiction_count": contradiction_count, "knowledge_gap_count": gap_count, "trace_count": trace_count, "inference_rules": ["direct_evidence_balance"], "duration_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000)})
    session.commit()
    return {"hypothesis_count": len(propositions), "contradiction_count": contradiction_count, "knowledge_gap_count": gap_count, "trace_count": trace_count, "confidence_semantics": "HelixMind evidence confidence"}
