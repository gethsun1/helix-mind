"""Persistence and graph queries for provenance-preserving knowledge."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.knowledge_extraction import DeterministicKnowledgeExtractor, claim_hash, normalize_claim, normalize_entity_name
from app.knowledge_metta import render_investigation_metta, validate_metta_text
from app.models import Claim, ClaimEntity, ClaimEvidence, Entity, Evidence, Investigation, InvestigationEvent, InvestigationPaper, Paper, Relationship, RelationshipClaim


def _event(session: Session, investigation_id: object, event_type: str, message: str, metadata: dict[str, Any]) -> None:
    session.add(InvestigationEvent(investigation_id=investigation_id, event_type=event_type, message=message, event_metadata=metadata, timestamp=datetime.now(timezone.utc)))


def _entity(session: Session, candidate, paper: Paper) -> Entity:
    normalized = normalize_entity_name(candidate.name)
    entity = session.scalar(select(Entity).where(Entity.entity_type == candidate.entity_type, Entity.normalized_name == normalized))
    if entity is None:
        entity = Entity(entity_type=candidate.entity_type, canonical_name=candidate.name, normalized_name=normalized, aliases=list(candidate.aliases) or None, entity_metadata={"source_papers": [str(paper.id)], "source_providers": [paper.source]})
        session.add(entity)
        session.flush()
        return entity
    aliases = set(entity.aliases or [])
    if candidate.name != entity.canonical_name:
        aliases.add(candidate.name)
    metadata = dict(entity.entity_metadata or {})
    metadata["source_papers"] = sorted(set(metadata.get("source_papers") or []) | {str(paper.id)})
    metadata["source_providers"] = sorted(set(metadata.get("source_providers") or []) | {paper.source})
    entity.aliases = sorted(aliases) or None
    entity.entity_metadata = metadata
    return entity


def _claim(session: Session, investigation_id: object, paper: Paper, candidate, entities: list[Entity]) -> Claim:
    digest = claim_hash(investigation_id, paper.id, candidate.text)
    claim = session.scalar(select(Claim).where(Claim.investigation_id == investigation_id, Claim.claim_hash == digest))
    if claim is None:
        claim = Claim(investigation_id=investigation_id, paper_id=paper.id, claim_text=candidate.text, normalized_text=normalize_claim(candidate.text), claim_hash=digest, extraction_method="deterministic_abstract", extraction_confidence=Decimal(str(candidate.extraction_confidence)), claim_metadata={"confidence_semantics": "extraction_confidence_not_truth_probability"})
        session.add(claim)
        session.flush()
    evidence = session.scalar(select(Evidence).where(Evidence.investigation_id == investigation_id, Evidence.paper_id == paper.id, Evidence.source_location == candidate.evidence.source_location, Evidence.source_span == {"start": candidate.evidence.start, "end": candidate.evidence.end}))
    if evidence is None:
        evidence = Evidence(investigation_id=investigation_id, paper_id=paper.id, evidence_type="ABSTRACT", extracted_text=candidate.evidence.text, strength=Decimal("0.000"), confidence=Decimal("0.000"), source_location=candidate.evidence.source_location, source_span={"start": candidate.evidence.start, "end": candidate.evidence.end}, section=candidate.evidence.section, retrieval_metadata={"retrieved_at": paper.retrieved_at.isoformat(), "provider": paper.source}, evidence_metadata={"confidence_semantics": "not_assessed"})
        session.add(evidence)
        session.flush()
    if session.scalar(select(ClaimEvidence).where(ClaimEvidence.claim_id == claim.id, ClaimEvidence.evidence_id == evidence.id)) is None:
        session.add(ClaimEvidence(claim_id=claim.id, evidence_id=evidence.id, role="DIRECT"))
    for entity in entities:
        if normalize_entity_name(entity.canonical_name) in normalize_claim(candidate.text) and session.scalar(select(ClaimEntity).where(ClaimEntity.claim_id == claim.id, ClaimEntity.entity_id == entity.id)) is None:
            session.add(ClaimEntity(claim_id=claim.id, entity_id=entity.id, role="MENTIONS"))
    _event(session, investigation_id, "knowledge_linked_to_evidence", "A claim was linked to its exact source evidence.", {"claim_id": str(claim.id), "evidence_id": str(evidence.id), "paper_id": str(paper.id)})
    return claim


def extract_investigation_knowledge(session: Session, investigation: Investigation) -> dict[str, int]:
    """Extract source-grounded knowledge idempotently from linked abstracts."""
    extractor = DeterministicKnowledgeExtractor()
    rows = session.execute(select(Paper).join(InvestigationPaper, InvestigationPaper.paper_id == Paper.id).where(InvestigationPaper.investigation_id == investigation.id)).scalars().unique().all()
    counts = {"papers": 0, "entities": 0, "claims": 0, "evidence": 0, "relationships": 0}
    _event(session, investigation.id, "knowledge_extraction_started", "Source-grounded knowledge extraction started.", {"extractor": extractor.name, "paper_count": len(rows)})
    session.commit()
    for paper in rows:
        result = extractor.extract(title=paper.title, abstract=paper.abstract, keywords=paper.keywords or [], mesh_terms=paper.mesh_terms or [])
        entities = [_entity(session, candidate, paper) for candidate in result.entities]
        counts["entities"] += len(entities)
        for entity in entities:
            _event(session, investigation.id, "entity_discovered", "A source-supported entity was recorded.", {"entity_id": str(entity.id), "paper_id": str(paper.id), "entity_type": entity.entity_type})
        entities_by_name = {normalize_entity_name(item.canonical_name): item for item in entities}
        claims_by_text: dict[str, Claim] = {}
        for candidate in result.claims:
            claim = _claim(session, investigation.id, paper, candidate, entities)
            claims_by_text[normalize_claim(candidate.text)] = claim
            counts["claims"] += 1
            counts["evidence"] += 1
            _event(session, investigation.id, "claim_extracted", "A source-grounded abstract claim was recorded.", {"claim_id": str(claim.id), "paper_id": str(paper.id), "source": paper.source, "source_location": candidate.evidence.source_location})
        for candidate in result.relationships:
            subject = entities_by_name.get(normalize_entity_name(candidate.subject))
            object_entity = entities_by_name.get(normalize_entity_name(candidate.object))
            claim = claims_by_text.get(normalize_claim(candidate.claim_text))
            if subject is None or object_entity is None or claim is None:
                continue
            relationship = session.scalar(select(Relationship).where(Relationship.investigation_id == investigation.id, Relationship.subject_entity_id == subject.id, Relationship.predicate == candidate.predicate, Relationship.object_entity_id == object_entity.id, Relationship.stance == "SUPPORTS"))
            if relationship is None:
                relationship = Relationship(investigation_id=investigation.id, subject_entity_id=subject.id, predicate=candidate.predicate, object_entity_id=object_entity.id, strength=Decimal("0.000"), confidence=Decimal("0.000"), source_type="LITERATURE_EXTRACTION", stance="SUPPORTS", relationship_metadata={"confidence_semantics": "not_assessed", "predicate_evidence": candidate.claim_text})
                session.add(relationship)
                session.flush()
                counts["relationships"] += 1
            if session.scalar(select(RelationshipClaim).where(RelationshipClaim.relationship_id == relationship.id, RelationshipClaim.claim_id == claim.id)) is None:
                session.add(RelationshipClaim(relationship_id=relationship.id, claim_id=claim.id))
            _event(session, investigation.id, "relationship_discovered", "An explicit source-supported relationship was recorded.", {"relationship_id": str(relationship.id), "claim_id": str(claim.id), "paper_id": str(paper.id), "predicate": candidate.predicate})
        counts["papers"] += 1
        session.commit()
    if counts["papers"]:
        metta_text = render_investigation_metta(session, investigation.id)
        validate_metta_text(metta_text)
        _event(session, investigation.id, "metta_fact_created", "Canonical knowledge was validated by the private MeTTa runtime.", {"fact_count": len([line for line in metta_text.splitlines() if line.startswith("(")]), "provenance": "database_claim_evidence_paper"})
    else:
        _event(session, investigation.id, "metta_validation_skipped", "No source-grounded knowledge was available for MeTTa validation.", {"reason": "no_abstract_knowledge"})
    _event(session, investigation.id, "knowledge_extraction_completed", "Source-grounded knowledge extraction completed.", {"extractor": extractor.name, **counts})
    session.commit()
    return counts


def investigation_graph(session: Session, investigation_id: object, *, query: str | None = None, limit: int = 200) -> dict[str, list[dict[str, Any]]]:
    entity_query = select(Entity).join(ClaimEntity, ClaimEntity.entity_id == Entity.id).join(Claim, Claim.id == ClaimEntity.claim_id).where(Claim.investigation_id == investigation_id).distinct().limit(limit)
    if query:
        term = f"%{query.strip()}%"
        entity_query = entity_query.where(or_(Entity.canonical_name.ilike(term), Entity.normalized_name.ilike(term)))
    entities = session.scalars(entity_query).all()
    entity_ids = {entity.id for entity in entities}
    relationships = session.scalars(select(Relationship).where(Relationship.investigation_id == investigation_id, Relationship.subject_entity_id.in_(entity_ids), Relationship.object_entity_id.in_(entity_ids)).limit(limit)).all() if entity_ids else []
    claim_ids = {claim_id for claim_id in session.scalars(select(RelationshipClaim.claim_id).where(RelationshipClaim.relationship_id.in_([item.id for item in relationships]))).all()}
    claims = {claim.id: claim for claim in session.scalars(select(Claim).where(Claim.id.in_(claim_ids))).all()} if claim_ids else {}
    paper_ids = {claim.paper_id for claim in claims.values()}
    papers = {paper.id: paper for paper in session.scalars(select(Paper).where(Paper.id.in_(paper_ids))).all()} if paper_ids else {}
    nodes = [{"id": str(entity.id), "type": "ENTITY", "label": entity.canonical_name, "entityType": entity.entity_type, "aliases": entity.aliases or []} for entity in entities]
    edges = []
    for relationship in relationships:
        related_claims = [claim for claim in claims.values() if session.scalar(select(RelationshipClaim).where(RelationshipClaim.relationship_id == relationship.id, RelationshipClaim.claim_id == claim.id)) is not None]
        edges.append({"id": str(relationship.id), "source": str(relationship.subject_entity_id), "target": str(relationship.object_entity_id), "relationship": relationship.predicate, "stance": relationship.stance, "claims": [{"id": str(claim.id), "text": claim.claim_text, "paperId": str(claim.paper_id), "paperTitle": papers[claim.paper_id].title if claim.paper_id in papers else None} for claim in related_claims]})
    return {"nodes": nodes, "edges": edges}
