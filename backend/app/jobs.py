import uuid
from datetime import datetime, timezone

from app.db import SessionLocal
from app.knowledge import extract_investigation_knowledge
from app.literature_pipeline import LiteraturePipelineError, run_literature_pipeline
from app.models import Investigation, InvestigationEvent, InvestigationRun
from app.omegaclaw_planning import OmegaClawPlanningError, run_research_planning
from app.research_reproducibility import create_run, digest_json, freeze_snapshot
from app.scientific_reasoning import run_scientific_reasoning


def _event(session, investigation_id, event_type: str, message: str, metadata: dict | None = None) -> None:
    session.add(
        InvestigationEvent(
            investigation_id=investigation_id,
            event_type=event_type,
            message=message,
            event_metadata=metadata,
            timestamp=datetime.now(timezone.utc),
        )
    )


def _mark_failed(session, investigation_id: str, run_id: uuid.UUID | None, message: str, category: str) -> None:
    session.rollback()
    investigation = session.get(Investigation, uuid.UUID(investigation_id))
    if investigation is None:
        return
    investigation.status = "FAILED"
    investigation.error_message = message
    if run_id is not None:
        run = session.get(InvestigationRun, run_id)
        if run is not None:
            run.status = "FAILED"
            run.error_message = message
            run.completed_at = datetime.now(timezone.utc)
    _event(session, investigation.id, "investigation_failed", message, {"category": category})
    session.commit()


def start_investigation(investigation_id: str, run_id: str | None = None) -> dict[str, object]:
    """Consume one queue item through planning, literature, and persistence."""
    session = SessionLocal()
    run_uuid = uuid.UUID(run_id) if run_id else None
    run: InvestigationRun | None = None
    active_run_id: uuid.UUID | None = run_uuid
    try:
        investigation = session.get(Investigation, uuid.UUID(investigation_id))
        if investigation is None:
            return {"status": "missing"}
        if investigation.status.upper() != "QUEUED":
            return {"status": investigation.status}

        run = session.get(InvestigationRun, run_uuid) if run_uuid else create_run(session, investigation)
        if run is None or run.investigation_id != investigation.id:
            return {"status": "missing"}
        if run_uuid is not None and run.status != "QUEUED":
            return {"status": run.status}
        active_run_id = run.id
        run.status = "RUNNING"
        run.started_at = datetime.now(timezone.utc)
        investigation.status = "PLANNING"
        investigation.started_at = datetime.now(timezone.utc)
        _event(session, investigation.id, "research_started", "Investigation accepted by the HelixMind research worker.", {"worker": "helixmind-worker", "run_id": str(run.id)})
        _event(session, investigation.id, "planning_started", "OmegaClaw is planning the research strategy.", {"orchestrator": "OmegaClaw", "run_id": str(run.id)})
        session.commit()
        plan = run_research_planning(
            title=investigation.title,
            research_question=investigation.question,
            domain=investigation.domain,
        )
        investigation.research_plan = plan
        run.plan_hash = digest_json(plan)
        run.provider_metadata = plan.get("_metadata", {}) if isinstance(plan, dict) else {}
        _event(
            session,
            investigation.id,
            "planning_completed",
            "OmegaClaw produced a structured research plan. Literature analysis has not started.",
            {"orchestrator": plan.get("_metadata", {}).get("orchestrator"), "provider": plan.get("_metadata", {}).get("provider"), "model": plan.get("_metadata", {}).get("model"), "run_id": str(run.id)},
        )
        session.commit()
        investigation = session.get(Investigation, uuid.UUID(investigation_id))
        assert investigation is not None
        investigation.status = "SEARCHING"
        _event(session, investigation.id, "literature_search_started", "Literature search is beginning from the persisted OmegaClaw strategy.", {"sources": ["PUBMED", "EUROPE_PMC"], "run_id": str(run.id)})
        session.commit()
        summary = run_literature_pipeline(session, investigation)
        investigation.status = "KNOWLEDGE"
        _event(session, investigation.id, "knowledge_stage_started", "Source-grounded knowledge extraction is beginning.", {"paper_count": summary.get("paper_count", 0), "run_id": str(run.id)})
        session.commit()
        knowledge_summary = extract_investigation_knowledge(session, investigation)
        reasoning_summary = None
        if knowledge_summary.get("papers", 0) > 0:
            investigation = session.get(Investigation, uuid.UUID(investigation_id))
            assert investigation is not None
            investigation.status = "REASONING"
            _event(session, investigation.id, "reasoning_stage_started", "HelixMind is analyzing evidence, hypotheses, contradictions, and knowledge gaps.", {"engine": "HelixMindEvidenceReasoner", "run_id": str(run.id)})
            session.commit()
            reasoning_summary = run_scientific_reasoning(session, investigation)
        investigation.status = "COMPLETED"
        investigation.completed_at = datetime.now(timezone.utc)
        run.status = "COMPLETED"
        run.completed_at = investigation.completed_at
        freeze_snapshot(session, investigation, run)
        session.commit()
        return {"status": "COMPLETED", "run_id": str(run.id), "snapshot": "persisted", "plan": "persisted", **summary, "knowledge": knowledge_summary, "reasoning": reasoning_summary}
    except LiteraturePipelineError as error:
        _mark_failed(session, investigation_id, active_run_id, str(error), error.category)
        return {"status": "FAILED"}
    except OmegaClawPlanningError as error:
        _mark_failed(session, investigation_id, active_run_id, str(error), error.category)
        return {"status": "FAILED"}
    except Exception:
        _mark_failed(session, investigation_id, active_run_id, "The research worker encountered an unexpected error.", "SYSTEM_ERROR")
        return {"status": "FAILED"}
    finally:
        session.close()
