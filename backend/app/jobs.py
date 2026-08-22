import uuid
from datetime import datetime, timezone

from app.db import SessionLocal
from app.literature_pipeline import LiteraturePipelineError, run_literature_pipeline
from app.models import Investigation, InvestigationEvent
from app.omegaclaw_planning import OmegaClawPlanningError, run_research_planning


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


def start_investigation(investigation_id: str) -> dict[str, object]:
    """Consume one queue item through planning, literature, and persistence."""
    session = SessionLocal()
    try:
        investigation = session.get(Investigation, uuid.UUID(investigation_id))
        if investigation is None:
            return {"status": "missing"}
        if investigation.status.upper() != "QUEUED":
            return {"status": investigation.status}

        investigation.status = "PLANNING"
        investigation.started_at = datetime.now(timezone.utc)
        _event(session, investigation.id, "research_started", "Investigation accepted by the HelixMind research worker.", {"worker": "helixmind-worker"})
        _event(session, investigation.id, "planning_started", "OmegaClaw is planning the research strategy.", {"orchestrator": "OmegaClaw"})
        session.commit()
        plan = run_research_planning(
            title=investigation.title,
            research_question=investigation.question,
            domain=investigation.domain,
        )
        investigation.research_plan = plan
        _event(
            session,
            investigation.id,
            "planning_completed",
            "OmegaClaw produced a structured research plan. Literature analysis has not started.",
            {"orchestrator": plan.get("_metadata", {}).get("orchestrator"), "provider": plan.get("_metadata", {}).get("provider"), "model": plan.get("_metadata", {}).get("model")},
        )
        session.commit()
        investigation = session.get(Investigation, uuid.UUID(investigation_id))
        assert investigation is not None
        investigation.status = "SEARCHING"
        _event(session, investigation.id, "literature_search_started", "Literature search is beginning from the persisted OmegaClaw strategy.", {"sources": ["PUBMED", "EUROPE_PMC"]})
        session.commit()
        summary = run_literature_pipeline(session, investigation)
        investigation.status = "COMPLETED"
        investigation.completed_at = datetime.now(timezone.utc)
        session.commit()
        return {"status": "COMPLETED", "plan": "persisted", **summary}
    except LiteraturePipelineError as error:
        session.rollback()
        investigation = session.get(Investigation, uuid.UUID(investigation_id))
        if investigation is not None and investigation.status.upper() != "CANCELLED":
            investigation.status = "FAILED"
            investigation.error_message = str(error)
            _event(session, investigation.id, "investigation_failed", str(error), {"category": error.category})
            session.commit()
        return {"status": "FAILED"}
    except OmegaClawPlanningError as error:
        session.rollback()
        investigation = session.get(Investigation, uuid.UUID(investigation_id))
        if investigation is not None and investigation.status.upper() != "CANCELLED":
            investigation.status = "FAILED"
            investigation.error_message = str(error)
            _event(session, investigation.id, "investigation_failed", str(error), {"category": error.category})
            session.commit()
        return {"status": "FAILED"}
    except Exception:
        session.rollback()
        investigation = session.get(Investigation, uuid.UUID(investigation_id))
        if investigation is not None and investigation.status.upper() != "CANCELLED":
            investigation.status = "FAILED"
            investigation.error_message = "The research worker encountered an unexpected error."
            _event(
                session,
                investigation.id,
                "investigation_failed",
                "The research worker encountered an unexpected error.",
                {"category": "SYSTEM_ERROR"},
            )
            session.commit()
        return {"status": "FAILED"}
    finally:
        session.close()
