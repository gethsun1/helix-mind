"""Derived research progress and health projections for the workstation UI."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Claim,
    Contradiction,
    Evidence,
    Hypothesis,
    Investigation,
    InvestigationEvent,
    InvestigationPaper,
    InvestigationRun,
    KnowledgeGap,
    Proposition,
    ResearchArtifact,
    ResearchSearch,
    ResearchSnapshot,
)


def _count(session: Session, model: Any, investigation_id: object) -> int:
    return int(session.scalar(select(func.count()).select_from(model).where(model.investigation_id == investigation_id)) or 0)


def _event_time(events: list[InvestigationEvent], event_types: set[str]) -> datetime | None:
    for event in events:
        if event.event_type in event_types:
            return event.timestamp
    return None


def research_health(session: Session, investigation_id: object) -> dict[str, int]:
    evidence = _count(session, Evidence, investigation_id)
    evidence_with_provenance = int(
        session.scalar(
            select(func.count())
            .select_from(Evidence)
            .where(
                Evidence.investigation_id == investigation_id,
                Evidence.paper_id.is_not(None),
                Evidence.source_span.is_not(None),
                Evidence.source_location.is_not(None),
            )
        )
        or 0
    )
    return {
        "papers": int(session.scalar(select(func.count(func.distinct(InvestigationPaper.paper_id))).where(InvestigationPaper.investigation_id == investigation_id)) or 0),
        "searches": _count(session, ResearchSearch, investigation_id),
        "claims": _count(session, Claim, investigation_id),
        "evidence": evidence,
        "evidence_with_provenance": evidence_with_provenance,
        "propositions": _count(session, Proposition, investigation_id),
        "hypotheses": _count(session, Hypothesis, investigation_id),
        "contradictions": _count(session, Contradiction, investigation_id),
        "knowledge_gaps": _count(session, KnowledgeGap, investigation_id),
    }


def research_milestones(session: Session, investigation: Investigation) -> list[dict[str, Any]]:
    events = session.scalars(
        select(InvestigationEvent)
        .where(InvestigationEvent.investigation_id == investigation.id)
        .order_by(InvestigationEvent.timestamp.asc(), InvestigationEvent.id.asc())
    ).all()
    health = research_health(session, investigation.id)
    completed_runs = int(session.scalar(select(func.count()).select_from(InvestigationRun).where(InvestigationRun.investigation_id == investigation.id, InvestigationRun.status == "COMPLETED")) or 0)
    completed_artifacts = int(
        session.scalar(
            select(func.count())
            .select_from(ResearchArtifact)
            .join(ResearchSnapshot, ResearchSnapshot.id == ResearchArtifact.snapshot_id)
            .where(ResearchSnapshot.investigation_id == investigation.id, ResearchArtifact.status == "COMPLETED")
        )
        or 0
    )
    conditions = [
        ("question", "Question formulated", bool(investigation.question.strip()), {"investigation_created"}, "Research question recorded."),
        ("literature", "Literature discovered", health["papers"] > 0, {"literature_search_completed", "pubmed_search_completed", "europe_pmc_search_completed"}, f"{health['papers']} canonical paper record(s)."),
        ("evidence", "Evidence mapped", health["evidence"] > 0, {"knowledge_extraction_completed"}, f"{health['evidence']} source-linked evidence record(s)."),
        ("knowledge", "Knowledge graph constructed", health["propositions"] > 0 or health["claims"] > 0, {"metta_fact_created"}, f"{health['claims']} claim(s) and {health['propositions']} proposition(s)."),
        ("hypotheses", "Hypotheses evaluated", health["hypotheses"] > 0, {"reasoning_completed"}, f"{health['hypotheses']} qualified hypothesis record(s)."),
        ("gaps", "Knowledge gaps discovered", health["knowledge_gaps"] > 0, {"knowledge_gap_detected"}, f"{health['knowledge_gaps']} knowledge gap record(s)."),
        ("reproduced", "Investigation reproduced", completed_runs >= 2, set(), f"{completed_runs} completed run(s)."),
        ("artifact", "Research artifact generated", completed_artifacts > 0, set(), f"{completed_artifacts} completed artifact(s)."),
    ]
    next_pending = next((index for index, item in enumerate(conditions) if not item[2]), None)
    result = []
    for index, (key, label, achieved, event_types, evidence) in enumerate(conditions):
        timestamp = _event_time(events, event_types) if event_types else None
        if achieved:
            state = "ACHIEVED"
        elif next_pending == index:
            state = "CURRENT"
        else:
            state = "PENDING"
        result.append({"key": key, "label": label, "status": state, "achieved_at": timestamp, "evidence": evidence})
    return result
