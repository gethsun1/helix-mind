import uuid

from app.db import SessionLocal
from app.literature import LiteratureClient, persist_papers
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

        session.add(
            InvestigationEvent(
                investigation_id=investigation.id,
                event_type="literature_search_started",
                message="Searching official PubMed and Europe PMC APIs.",
                event_metadata={"sources": ["pubmed", "europepmc"]},
            )
        )
        session.commit()

        client = LiteratureClient()
        try:
            candidates, failures = client.search_all(investigation.question)
        finally:
            client.close()
        papers = persist_papers(session, investigation.id, investigation.question, candidates)

        if papers:
            session.add(
                InvestigationEvent(
                    investigation_id=investigation.id,
                    event_type="papers_found",
                    message=f"Retrieved and normalized {len(papers)} distinct papers.",
                    event_metadata={"count": len(papers), "source_failures": failures},
                )
            )
            for paper in papers:
                session.add(
                    InvestigationEvent(
                        investigation_id=investigation.id,
                        event_type="paper_ingested",
                        message=f"Ingested {paper.title}",
                        event_metadata={"paper_id": str(paper.id), "source": paper.source, "external_id": paper.external_id},
                    )
                )
        if failures:
            session.add(
                InvestigationEvent(
                    investigation_id=investigation.id,
                    event_type="literature_source_failed",
                    message="One or more literature sources were unavailable; no results were fabricated.",
                    event_metadata={"sources": failures},
                )
            )

        investigation.status = "literature_ready"
        session.add(
            InvestigationEvent(
                investigation_id=investigation.id,
                event_type="literature_search_completed",
                message="Literature retrieval stage completed with persisted source provenance.",
                event_metadata={"papers": len(papers), "source_failures": failures},
            )
        )
        session.commit()
        return {"status": "literature_ready", "papers": str(len(papers))}
    finally:
        session.close()
