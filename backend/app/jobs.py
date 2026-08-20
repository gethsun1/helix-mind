import uuid

from app.db import SessionLocal
from app.models import Investigation, InvestigationEvent


def start_investigation(investigation_id: str) -> dict[str, str]:
    """Advance a queued investigation to the real orchestration checkpoint.

    OmegaClaw work is deliberately not simulated here. This job provides the
    verified async boundary which the actual orchestrator will consume.
    """
    session = SessionLocal()
    try:
        investigation = session.get(Investigation, uuid.UUID(investigation_id))
        if investigation is None:
            return {"status": "missing"}
        if investigation.status != "queued":
            return {"status": investigation.status}

        investigation.status = "planning"
        session.add(
            InvestigationEvent(
                investigation_id=investigation.id,
                event_type="research_started",
                message="Investigation accepted by the HelixMind research worker.",
                event_metadata={"worker": "helixmind-worker"},
            )
        )
        session.commit()
        return {"status": "planning"}
    finally:
        session.close()
