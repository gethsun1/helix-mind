from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.literature import EUROPE_PMC, PUBMED, LiteratureClient, LiteratureError, NormalizedPaper, build_search_strategy, deduplicate_papers, persist_papers, rank_investigation_papers
from app.models import Investigation, InvestigationEvent, InvestigationPaper, Paper, ResearchSearch


class LiteraturePipelineError(RuntimeError):
    def __init__(self, message: str, category: str = "EXTERNAL_PROVIDER_ERROR") -> None:
        super().__init__(message)
        self.category = category


def _event(session: Session, investigation_id: object, event_type: str, message: str, metadata: dict[str, Any] | None = None) -> None:
    session.add(InvestigationEvent(investigation_id=investigation_id, event_type=event_type, message=message, event_metadata=metadata, timestamp=datetime.now(timezone.utc)))


def _cache_key(source: str, query: str, filters: dict[str, Any]) -> str:
    payload = json.dumps({"source": source, "query": query, "filters": filters}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _paper_candidate(paper: Paper, source: str, query: str) -> NormalizedPaper:
    metadata = dict(paper.paper_metadata or {})
    metadata["source_records"] = sorted(set(metadata.get("source_records") or []) | {source})
    metadata["search_query"] = query
    return NormalizedPaper(
        source=source, external_id=paper.external_id, title=paper.title, abstract=paper.abstract, authors=paper.authors or [],
        publication_date=paper.publication_date, doi=paper.doi, url=paper.url, metadata=metadata, journal=paper.journal,
        pmid=paper.pmid, pmcid=paper.pmcid, publication_type=paper.publication_type or [], language=paper.language,
        mesh_terms=paper.mesh_terms or [], keywords=paper.keywords or [],
    )


def _cached_papers(session: Session, search: ResearchSearch) -> list[NormalizedPaper]:
    rows = session.execute(select(Paper).join(InvestigationPaper, InvestigationPaper.paper_id == Paper.id).where(InvestigationPaper.research_search_id == search.id)).scalars().all()
    return [_paper_candidate(paper, search.source, search.query) for paper in rows]


def run_literature_pipeline(session: Session, investigation: Investigation) -> dict[str, Any]:
    """Run both official source searches, persist provenance, and rank relevance."""
    plan = dict(investigation.research_plan or {})
    try:
        strategy = build_search_strategy(plan, investigation.question)
    except LiteratureError as error:
        raise LiteraturePipelineError(str(error), "INVALID_RESEARCH_PLAN") from error

    plan["search_strategy"] = strategy
    investigation.research_plan = plan
    _event(session, investigation.id, "search_strategy_created", "Search strategy derived from the OmegaClaw research plan.", {"sources": [PUBMED, EUROPE_PMC]})
    session.commit()

    client = LiteratureClient()
    all_papers: list[NormalizedPaper] = []
    failures: dict[str, str] = {}
    search_ids: dict[str, object] = {}
    try:
        for source, query in ((PUBMED, strategy["pubmed"]), (EUROPE_PMC, strategy["europe_pmc"])):
            filters: dict[str, Any] = {}
            cache_key = _cache_key(source, query, filters)
            search = session.scalar(select(ResearchSearch).where(ResearchSearch.investigation_id == investigation.id, ResearchSearch.source == source, ResearchSearch.cache_key == cache_key, ResearchSearch.status == "SUCCEEDED", ResearchSearch.executed_at >= datetime.now(timezone.utc) - timedelta(hours=24)).order_by(ResearchSearch.executed_at.desc()))
            if search is not None:
                search.reused = True
                search_ids[source] = search.id
                cached = _cached_papers(session, search)
                all_papers.extend(cached)
                _event(session, investigation.id, f"{source.lower()}_search_reused", f"{source} search reused — {len(cached)} persisted records.", {"search_id": str(search.id), "reused": True})
                session.commit()
                continue

            search = ResearchSearch(investigation_id=investigation.id, source=source, query=query, filters=filters, cache_key=cache_key, status="RUNNING")
            session.add(search)
            session.flush()
            search_ids[source] = search.id
            _event(session, investigation.id, "pubmed_search_started" if source == PUBMED else "europe_pmc_search_started", f"{source} search started.", {"query": query, "search_id": str(search.id)})
            session.commit()
            try:
                result = client.search_pubmed_result(query, filters=filters) if source == PUBMED else client.search_europe_pmc_result(query, filters=filters)
                search = session.get(ResearchSearch, search.id)
                assert search is not None
                search.status = "SUCCEEDED"
                search.result_count = len(result.papers)
                all_papers.extend(result.papers)
                event_type = "pubmed_search_completed" if source == PUBMED else "europe_pmc_search_completed"
                _event(session, investigation.id, event_type, f"{source} search completed — {len(result.papers)} records retrieved.", {"search_id": str(search.id), "source_total": result.total_count, "result_count": len(result.papers), "query": query})
                session.commit()
            except LiteratureError as error:
                search = session.get(ResearchSearch, search.id)
                if search is not None:
                    search.status = "FAILED"
                    search.error_message = str(error)
                failures[source] = type(error).__name__
                _event(session, investigation.id, "pubmed_search_failed" if source == PUBMED else "europe_pmc_search_failed", f"{source} search failed; the other source will continue if available.", {"search_id": str(search.id), "category": "EXTERNAL_PROVIDER_ERROR"})
                session.commit()
    finally:
        client.close()

    unique_papers, duplicate_count = deduplicate_papers(all_papers)
    _event(session, investigation.id, "papers_normalized", f"{len(all_papers)} source records normalized.", {"record_count": len(all_papers)})
    _event(session, investigation.id, "papers_deduplicated", f"{len(unique_papers)} unique papers identified after deduplication.", {"unique_count": len(unique_papers), "duplicates_removed": duplicate_count})
    session.commit()

    if not all_papers and len(failures) == 2:
        _event(session, investigation.id, "literature_search_failed", "All scientific literature sources failed; no papers were fabricated.", {"failures": failures})
        session.commit()
        raise LiteraturePipelineError("All scientific literature sources failed.", "EXTERNAL_PROVIDER_ERROR")

    persisted = persist_papers(session, investigation.id, strategy["pubmed"], unique_papers, research_search_ids=search_ids)
    _event(session, investigation.id, "papers_persisted", f"{len(persisted)} papers persisted and linked to the investigation.", {"persisted_count": len(persisted), "partial_failures": failures})
    rank_investigation_papers(session, investigation.id, plan)
    _event(session, investigation.id, "literature_search_completed", f"Literature search completed — {len(persisted)} unique papers available.", {"paper_count": len(persisted), "duplicates_removed": duplicate_count, "partial_failures": failures})
    session.commit()
    return {"paper_count": len(persisted), "normalized_count": len(all_papers), "duplicates_removed": duplicate_count, "failures": failures, "partial": bool(failures)}
