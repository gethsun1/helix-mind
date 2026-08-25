"""Phase 4A run, snapshot, and comparison contracts.

Snapshots are immutable projections of the canonical PostgreSQL investigation
graph. They are not a second source of scientific truth and never contain
provider credentials.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.knowledge_metta import render_investigation_metta
from app.models import (
    Claim,
    ClaimEntity,
    Contradiction,
    Entity,
    Evidence,
    Hypothesis,
    Inference,
    Investigation,
    InvestigationEvent,
    InvestigationPaper,
    InvestigationRun,
    KnowledgeGap,
    Paper,
    Proposition,
    Relationship,
    RelationshipClaim,
    ResearchSearch,
    ResearchSnapshot,
)


REPRODUCIBILITY_SCHEMA_VERSION = "phase4a-1"
FORMULA_VERSION = "3E-1"
ARTIFACT_CONTRACT_VERSION = "phase4a-artifact-1"
SAFE_METADATA_KEYS = {
    "adapter",
    "category",
    "duration_ms",
    "engine",
    "event_id",
    "fallback_occurred",
    "formula_version",
    "inference_rules",
    "model",
    "orchestrator",
    "provider",
    "reasoning_stage",
    "source",
    "sources",
    "trace_count",
    "type",
    "worker",
}


def _json_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_json_value(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _safe_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    return {key: _json_value(item) for key, item in value.items() if key in SAFE_METADATA_KEYS}


def _record_digest(record: dict[str, Any]) -> str:
    return digest_json(record)


def _investigation_input(investigation: Investigation) -> dict[str, Any]:
    return {
        "investigation_id": str(investigation.id),
        "title": investigation.title,
        "question": investigation.question,
        "domain": investigation.domain,
        "research_plan": _json_value(investigation.research_plan or {}),
    }


def _paper_records(session: Session, investigation_id: object) -> list[dict[str, Any]]:
    rows = session.execute(
        select(Paper, InvestigationPaper)
        .join(InvestigationPaper, InvestigationPaper.paper_id == Paper.id)
        .where(InvestigationPaper.investigation_id == investigation_id)
    ).all()
    records = []
    for paper, link in rows:
        record = {
            "id": str(paper.id),
            "source": paper.source,
            "external_id": paper.external_id,
            "title": paper.title,
            "abstract": paper.abstract,
            "authors": paper.authors or [],
            "journal": paper.journal,
            "publication_date": paper.publication_date,
            "publication_type": paper.publication_type or [],
            "language": paper.language,
            "mesh_terms": paper.mesh_terms or [],
            "keywords": paper.keywords or [],
            "doi": paper.doi,
            "pmid": paper.pmid,
            "pmcid": paper.pmcid,
            "url": paper.url,
            "full_text_url": paper.full_text_url,
            "publisher_identifier": paper.publisher_identifier,
            "journal_metadata": paper.journal_metadata or {},
            "paper_metadata": paper.paper_metadata or {},
            "retrieved_at": paper.retrieved_at,
            "investigation_paper": {
                "source": link.source,
                "source_query": link.source_query,
                "research_search_id": link.research_search_id,
                "relevance_score": link.relevance_score,
                "relevance_reason": link.relevance_reason,
                "discovered_at": link.discovered_at,
                "selected": link.selected,
                "rank": link.rank,
            },
        }
        record["record_digest"] = _record_digest(record)
        records.append(_json_value(record))
    return sorted(records, key=lambda item: item["id"])


def _search_records(session: Session, investigation_id: object) -> list[dict[str, Any]]:
    rows = session.scalars(select(ResearchSearch).where(ResearchSearch.investigation_id == investigation_id)).all()
    records = []
    for item in rows:
        record = {
            "id": item.id,
            "source": item.source,
            "query": item.query,
            "filters": item.filters or {},
            "cache_key": item.cache_key,
            "executed_at": item.executed_at,
            "result_count": item.result_count,
            "status": item.status,
            "error_message": item.error_message,
            "reused": item.reused,
        }
        record["record_digest"] = _record_digest(record)
        records.append(_json_value(record))
    return sorted(records, key=lambda item: item["id"])


def _claim_records(session: Session, investigation_id: object) -> list[dict[str, Any]]:
    rows = session.scalars(select(Claim).where(Claim.investigation_id == investigation_id)).all()
    records = []
    for item in rows:
        record = {
            "id": item.id,
            "paper_id": item.paper_id,
            "proposition_id": item.proposition_id,
            "claim_text": item.claim_text,
            "normalized_text": item.normalized_text,
            "claim_hash": item.claim_hash,
            "extraction_method": item.extraction_method,
            "extraction_confidence": item.extraction_confidence,
            "metadata": item.claim_metadata or {},
        }
        record["record_digest"] = _record_digest(record)
        records.append(_json_value(record))
    return sorted(records, key=lambda item: item["id"])


def _evidence_records(session: Session, investigation_id: object) -> list[dict[str, Any]]:
    rows = session.scalars(select(Evidence).where(Evidence.investigation_id == investigation_id)).all()
    records = []
    for item in rows:
        record = {
            "id": item.id,
            "paper_id": item.paper_id,
            "proposition_id": item.proposition_id,
            "relationship_id": item.relationship_id,
            "evidence_type": item.evidence_type,
            "extracted_text": item.extracted_text,
            "source_location": item.source_location,
            "source_span": item.source_span,
            "section": item.section,
            "retrieval_metadata": item.retrieval_metadata or {},
            "extraction_timestamp": item.extraction_timestamp,
            "strength": item.strength,
            "confidence": item.confidence,
            "polarity": item.polarity,
            "extraction_method": item.extraction_method,
            "metadata": item.evidence_metadata or {},
        }
        record["record_digest"] = _record_digest(record)
        records.append(_json_value(record))
    return sorted(records, key=lambda item: item["id"])


def _entity_records(session: Session, investigation_id: object) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Entity)
        .join(ClaimEntity, ClaimEntity.entity_id == Entity.id)
        .join(Claim, Claim.id == ClaimEntity.claim_id)
        .where(Claim.investigation_id == investigation_id)
        .distinct()
    ).all()
    records = []
    for item in rows:
        record = {
            "id": item.id,
            "entity_type": item.entity_type,
            "canonical_name": item.canonical_name,
            "normalized_name": item.normalized_name,
            "aliases": item.aliases or [],
            "description": item.description,
            "metadata": item.entity_metadata or {},
        }
        record["record_digest"] = _record_digest(record)
        records.append(_json_value(record))
    return sorted(records, key=lambda item: item["id"])


def _relationship_records(session: Session, investigation_id: object) -> list[dict[str, Any]]:
    rows = session.scalars(select(Relationship).where(Relationship.investigation_id == investigation_id)).all()
    records = []
    for item in rows:
        claim_ids = session.scalars(select(RelationshipClaim.claim_id).where(RelationshipClaim.relationship_id == item.id)).all()
        record = {
            "id": item.id,
            "subject_entity_id": item.subject_entity_id,
            "predicate": item.predicate,
            "object_entity_id": item.object_entity_id,
            "strength": item.strength,
            "confidence": item.confidence,
            "source_type": item.source_type,
            "stance": item.stance,
            "claim_ids": claim_ids,
            "metadata": item.relationship_metadata or {},
        }
        record["record_digest"] = _record_digest(record)
        records.append(_json_value(record))
    return sorted(records, key=lambda item: item["id"])


def _simple_records(session: Session, model: Any, investigation_id: object, fields: tuple[str, ...]) -> list[dict[str, Any]]:
    rows = session.scalars(select(model).where(model.investigation_id == investigation_id)).all()
    records = []
    for item in rows:
        record = {field: getattr(item, field) for field in fields}
        record["id"] = item.id
        record["record_digest"] = _record_digest(record)
        records.append(_json_value(record))
    return sorted(records, key=lambda item: item["id"])


def _provider_events(session: Session, investigation_id: object) -> list[dict[str, Any]]:
    events = session.scalars(
        select(InvestigationEvent)
        .where(InvestigationEvent.investigation_id == investigation_id)
        .order_by(InvestigationEvent.timestamp.asc(), InvestigationEvent.id.asc())
    ).all()
    records = []
    for event in events:
        metadata = _safe_metadata(event.event_metadata)
        if not metadata or not any(key in metadata for key in ("provider", "model", "orchestrator", "category")):
            continue
        records.append({"event_id": str(event.id), "event_type": event.event_type, "timestamp": event.timestamp.isoformat(), "metadata": metadata})
    return records


def create_run(session: Session, investigation: Investigation, *, parent_run_id: object | None = None, status: str = "QUEUED") -> InvestigationRun:
    latest_number = session.scalar(select(func.max(InvestigationRun.run_number)).where(InvestigationRun.investigation_id == investigation.id)) or 0
    if parent_run_id is None:
        parent_run_id = session.scalar(
            select(InvestigationRun.id)
            .where(InvestigationRun.investigation_id == investigation.id)
            .order_by(InvestigationRun.run_number.desc())
            .limit(1)
        )
    run = InvestigationRun(
        investigation_id=investigation.id,
        parent_run_id=parent_run_id,
        run_number=latest_number + 1,
        status=status,
        code_version=os.getenv("HELIXMIND_CODE_VERSION", "unknown"),
        schema_version=REPRODUCIBILITY_SCHEMA_VERSION,
        input_manifest=_investigation_input(investigation),
    )
    session.add(run)
    session.flush()
    return run


def build_snapshot_manifest(session: Session, investigation: Investigation, run: InvestigationRun) -> tuple[dict[str, Any], str, str]:
    metta_text = render_investigation_metta(session, investigation.id)
    metta_digest = hashlib.sha256(metta_text.encode("utf-8")).hexdigest()
    events = session.scalars(
        select(InvestigationEvent)
        .where(InvestigationEvent.investigation_id == investigation.id)
        .order_by(InvestigationEvent.timestamp.asc(), InvestigationEvent.id.asc())
    ).all()
    formula_version = next(
        (event.event_metadata.get("formula_version") for event in events if event.event_type == "reasoning_started" and event.event_metadata and event.event_metadata.get("formula_version")),
        FORMULA_VERSION,
    )
    manifest: dict[str, Any] = {
        "schema_version": REPRODUCIBILITY_SCHEMA_VERSION,
        "investigation": _investigation_input(investigation),
        "run": {
            "id": run.id,
            "run_number": run.run_number,
            "parent_run_id": run.parent_run_id,
            "status": run.status,
            "code_version": run.code_version,
            "schema_version": run.schema_version,
            "plan_hash": run.plan_hash,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
        },
        "formula_version": formula_version,
        "metta_digest": metta_digest,
        "papers": _paper_records(session, investigation.id),
        "searches": _search_records(session, investigation.id),
        "claims": _claim_records(session, investigation.id),
        "evidence": _evidence_records(session, investigation.id),
        "entities": _entity_records(session, investigation.id),
        "relationships": _relationship_records(session, investigation.id),
        "propositions": _simple_records(session, Proposition, investigation.id, ("subject", "predicate", "object", "normalized_subject", "normalized_predicate", "normalized_object", "proposition_key", "description", "context", "provenance")),
        "hypotheses": _simple_records(session, Hypothesis, investigation.id, ("proposition_id", "statement", "description", "strength", "confidence", "status", "supporting_evidence_count", "contradictory_evidence_count", "uncertainty", "provenance")),
        "inferences": [
            _json_value({
                "id": item.id,
                "hypothesis_id": item.hypothesis_id,
                "rule_name": item.rule_name,
                "reasoning_summary": item.reasoning_summary,
                "strength": item.strength,
                "confidence": item.confidence,
                "metadata": item.inference_metadata or {},
                "created_at": item.created_at,
                "record_digest": _record_digest({"id": item.id, "hypothesis_id": item.hypothesis_id, "rule_name": item.rule_name, "reasoning_summary": item.reasoning_summary, "strength": item.strength, "confidence": item.confidence, "metadata": item.inference_metadata or {}, "created_at": item.created_at}),
            })
            for item in sorted(
                session.scalars(select(Inference).join(Hypothesis, Hypothesis.id == Inference.hypothesis_id).where(Hypothesis.investigation_id == investigation.id)).all(),
                key=lambda value: str(value.id),
            )
        ],
        "contradictions": _simple_records(session, Contradiction, investigation.id, ("proposition_id", "supporting_evidence_id", "contradictory_evidence_id", "contradiction_type", "context", "confidence", "provenance", "created_at")),
        "knowledge_gaps": _simple_records(session, KnowledgeGap, investigation.id, ("hypothesis_id", "proposition_id", "description", "severity", "status", "evidence_count", "contradiction_count", "confidence", "rationale", "research_opportunity", "related_entity_ids", "provenance", "created_at")),
        "events": [
            {"id": str(event.id), "type": event.event_type, "message": event.message, "metadata": _safe_metadata(event.event_metadata), "timestamp": event.timestamp.isoformat()}
            for event in events
        ],
        "provider_metadata": _provider_events(session, investigation.id),
        "artifact_contract": {
            "contract_version": ARTIFACT_CONTRACT_VERSION,
            "supported_formats": ["markdown", "scientific_report", "obsidian_vault"],
            "source_manifest_digest": "snapshot.manifest_digest",
        },
    }
    safe_manifest = _json_value(manifest)
    return safe_manifest, digest_json(safe_manifest), metta_digest


def freeze_snapshot(session: Session, investigation: Investigation, run: InvestigationRun, *, created_by_user_id: object | None = None) -> ResearchSnapshot:
    existing = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.run_id == run.id))
    if existing is not None:
        return existing
    if run.status != "COMPLETED":
        raise ValueError("Only completed investigation runs can be snapshotted.")
    snapshot_number = (session.scalar(select(func.max(ResearchSnapshot.snapshot_number)).where(ResearchSnapshot.investigation_id == investigation.id)) or 0) + 1
    manifest, manifest_digest, metta_digest = build_snapshot_manifest(session, investigation, run)
    snapshot = ResearchSnapshot(
        investigation_id=investigation.id,
        run_id=run.id,
        created_by_user_id=created_by_user_id,
        snapshot_number=snapshot_number,
        schema_version=REPRODUCIBILITY_SCHEMA_VERSION,
        formula_version=str(manifest["formula_version"]),
        metta_digest=metta_digest,
        manifest_digest=manifest_digest,
        manifest=manifest,
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def latest_completed_run(session: Session, investigation_id: object) -> InvestigationRun | None:
    return session.scalar(
        select(InvestigationRun)
        .where(InvestigationRun.investigation_id == investigation_id, InvestigationRun.status == "COMPLETED")
        .order_by(InvestigationRun.run_number.desc())
        .limit(1)
    )


def compare_snapshots(left: ResearchSnapshot, right: ResearchSnapshot) -> dict[str, Any]:
    if left.investigation_id != right.investigation_id:
        raise ValueError("Snapshots must belong to the same investigation.")
    sections = (
        "papers",
        "searches",
        "claims",
        "evidence",
        "entities",
        "relationships",
        "propositions",
        "hypotheses",
        "inferences",
        "contradictions",
        "knowledge_gaps",
    )
    result: dict[str, Any] = {
        "left_snapshot_id": str(left.id),
        "right_snapshot_id": str(right.id),
        "investigation_id": str(left.investigation_id),
        "sections": {},
        "provider_metadata_changed": left.manifest.get("provider_metadata", []) != right.manifest.get("provider_metadata", []),
        "formula_version_changed": left.manifest.get("formula_version") != right.manifest.get("formula_version"),
    }
    for section in sections:
        left_records = {str(item["id"]): item for item in left.manifest.get(section, [])}
        right_records = {str(item["id"]): item for item in right.manifest.get(section, [])}
        added = sorted(set(right_records) - set(left_records))
        removed = sorted(set(left_records) - set(right_records))
        changed = []
        for record_id in sorted(set(left_records) & set(right_records)):
            if left_records[record_id].get("record_digest") != right_records[record_id].get("record_digest"):
                changed.append({"id": record_id, "before": left_records[record_id], "after": right_records[record_id]})
        result["sections"][section] = {"added_ids": added, "removed_ids": removed, "changed": changed}
    result["summary"] = {
        "added": sum(len(value["added_ids"]) for value in result["sections"].values()),
        "removed": sum(len(value["removed_ids"]) for value in result["sections"].values()),
        "changed": sum(len(value["changed"]) for value in result["sections"].values()),
    }
    return result
