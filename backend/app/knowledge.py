"""Persistence and graph queries for provenance-preserving knowledge."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.knowledge_extraction import DeterministicKnowledgeExtractor, claim_hash, normalize_claim, normalize_entity_name
from app.knowledge_metta import render_investigation_metta, validate_metta_text
from app.models import Claim, ClaimEntity, ClaimEvidence, Entity, Evidence, Hypothesis, Investigation, InvestigationEvent, InvestigationPaper, InvestigationRun, KnowledgeGap, Paper, Proposition, Relationship, RelationshipClaim, ResearchSnapshot
from app.research_reproducibility import scoped_snapshot_manifest
from app.scientific_reasoning import evidence_polarity, normalize_proposition_part, proposition_key


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
        evidence = Evidence(investigation_id=investigation_id, paper_id=paper.id, evidence_type="ABSTRACT", extracted_text=candidate.evidence.text, strength=Decimal("0.600"), confidence=Decimal(str(candidate.extraction_confidence)), source_location=candidate.evidence.source_location, source_span={"start": candidate.evidence.start, "end": candidate.evidence.end}, section=candidate.evidence.section, retrieval_metadata={"retrieved_at": paper.retrieved_at.isoformat(), "provider": paper.source}, polarity=None, extraction_method=candidate.evidence.source_location + ":" + "deterministic_abstract", evidence_metadata={"confidence_semantics": "extraction_signal_not_truth_probability", "strength_semantics": "abstract_evidence_assessment_signal"})
        session.add(evidence)
        session.flush()
    if session.scalar(select(ClaimEvidence).where(ClaimEvidence.claim_id == claim.id, ClaimEvidence.evidence_id == evidence.id)) is None:
        session.add(ClaimEvidence(claim_id=claim.id, evidence_id=evidence.id, role="DIRECT"))
        session.flush()
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
            _event(session, investigation.id, "evidence_extracted", "An exact source span was persisted as evidence.", {"evidence_type": "ABSTRACT", "paper_id": str(paper.id), "claim_id": str(claim.id), "extraction_method": extractor.name})
            _event(session, investigation.id, "claim_extracted", "A source-grounded abstract claim was recorded.", {"claim_id": str(claim.id), "paper_id": str(paper.id), "source": paper.source, "source_location": candidate.evidence.source_location})
        for candidate in result.relationships:
            subject = entities_by_name.get(normalize_entity_name(candidate.subject))
            object_entity = entities_by_name.get(normalize_entity_name(candidate.object))
            claim = claims_by_text.get(normalize_claim(candidate.claim_text))
            if subject is None or object_entity is None or claim is None:
                continue
            normalized_subject = normalize_proposition_part(subject.canonical_name)
            normalized_predicate = normalize_proposition_part(candidate.predicate)
            normalized_object = normalize_proposition_part(object_entity.canonical_name)
            key = proposition_key(investigation.id, subject.canonical_name, candidate.predicate, object_entity.canonical_name)
            proposition = session.scalar(select(Proposition).where(Proposition.investigation_id == investigation.id, Proposition.proposition_key == key))
            if proposition is None:
                proposition = Proposition(
                    investigation_id=investigation.id,
                    subject=subject.canonical_name,
                    predicate=candidate.predicate,
                    object=object_entity.canonical_name,
                    normalized_subject=normalized_subject,
                    normalized_predicate=normalized_predicate,
                    normalized_object=normalized_object,
                    proposition_key=key,
                    description=f"{subject.canonical_name} {candidate.predicate.lower().replace('_', ' ')} {object_entity.canonical_name}.",
                    context={"source_location": "abstract", "extraction_method": extractor.name},
                    provenance={"claim_id": str(claim.id), "paper_id": str(paper.id), "provider": paper.source},
                )
                session.add(proposition)
                session.flush()
                _event(session, investigation.id, "proposition_created", "A structured proposition was derived from a source-linked claim.", {"proposition_id": str(proposition.id), "claim_id": str(claim.id), "paper_id": str(paper.id)})
            claim.proposition_id = proposition.id
            claim_evidence = session.scalars(select(Evidence).join(ClaimEvidence, ClaimEvidence.evidence_id == Evidence.id).where(ClaimEvidence.claim_id == claim.id)).all()
            polarity = evidence_polarity(claim.claim_text)
            for evidence in claim_evidence:
                evidence.proposition_id = proposition.id
                evidence.polarity = polarity
                evidence.extraction_method = extractor.name
                if not evidence.confidence or float(evidence.confidence) == 0:
                    evidence.confidence = claim.extraction_confidence or Decimal("0.990")
                if not evidence.strength or float(evidence.strength) == 0:
                    evidence.strength = Decimal("0.600")
                evidence.evidence_metadata = {**(evidence.evidence_metadata or {}), "polarity_reason": "explicit_source_sentence_cue" if polarity != "SUPPORTS" else "no_opposing_source_cue"}
            relationship = session.scalar(select(Relationship).where(Relationship.investigation_id == investigation.id, Relationship.subject_entity_id == subject.id, Relationship.predicate == candidate.predicate, Relationship.object_entity_id == object_entity.id, Relationship.stance == polarity))
            if relationship is None:
                relationship = Relationship(investigation_id=investigation.id, subject_entity_id=subject.id, predicate=candidate.predicate, object_entity_id=object_entity.id, strength=Decimal("0.600"), confidence=claim.extraction_confidence or Decimal("0.990"), source_type="LITERATURE_EXTRACTION", stance=polarity, relationship_metadata={"confidence_semantics": "extraction_signal_not_truth_probability", "predicate_evidence": candidate.claim_text, "proposition_id": str(proposition.id)})
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
    # Entity rows are shared across investigations, so their aggregated aliases
    # are not safe to expose without alias-level scoped provenance.
    nodes = [{"id": str(entity.id), "type": "ENTITY", "label": entity.canonical_name, "entityType": entity.entity_type, "aliases": []} for entity in entities]
    edges = []
    for relationship in relationships:
        related_claims = [claim for claim in claims.values() if session.scalar(select(RelationshipClaim).where(RelationshipClaim.relationship_id == relationship.id, RelationshipClaim.claim_id == claim.id)) is not None]
        edges.append({"id": str(relationship.id), "source": str(relationship.subject_entity_id), "target": str(relationship.object_entity_id), "relationship": relationship.predicate, "stance": relationship.stance, "provenance": relationship.relationship_metadata, "claims": [{"id": str(claim.id), "text": claim.claim_text, "paperId": str(claim.paper_id), "paperTitle": papers[claim.paper_id].title if claim.paper_id in papers else None} for claim in related_claims]})
    propositions = session.scalars(select(Proposition).where(Proposition.investigation_id == investigation_id).limit(limit)).all()
    proposition_ids = {item.id for item in propositions}
    nodes.extend({"id": str(item.id), "type": "PROPOSITION", "label": item.description, "entityType": "PROPOSITION", "aliases": []} for item in propositions)
    proposition_evidence = session.scalars(select(Evidence).where(Evidence.investigation_id == investigation_id, Evidence.proposition_id.in_(proposition_ids)).limit(limit)).all() if proposition_ids else []
    nodes.extend({"id": str(item.id), "type": "EVIDENCE", "label": item.extracted_text[:96], "entityType": item.polarity or "EVIDENCE", "aliases": []} for item in proposition_evidence)
    edges.extend({"id": f"evidence-{item.id}", "source": str(item.id), "target": str(item.proposition_id), "relationship": item.polarity or "EVIDENCE", "stance": item.polarity, "provenance": {"paper_id": str(item.paper_id) if item.paper_id else None, "source_span": item.source_span}, "claims": []} for item in proposition_evidence)
    hypotheses = session.scalars(select(Hypothesis).where(Hypothesis.investigation_id == investigation_id, Hypothesis.proposition_id.in_(proposition_ids)).limit(limit)).all() if proposition_ids else []
    nodes.extend({"id": str(item.id), "type": "HYPOTHESIS", "label": item.statement, "entityType": item.status, "aliases": []} for item in hypotheses)
    edges.extend({"id": f"hypothesis-{item.id}", "source": str(item.id), "target": str(item.proposition_id), "relationship": "HYPOTHESIS_FOR", "stance": item.status, "provenance": item.provenance, "claims": []} for item in hypotheses)
    gaps = session.scalars(select(KnowledgeGap).where(KnowledgeGap.investigation_id == investigation_id, KnowledgeGap.proposition_id.in_(proposition_ids)).limit(limit)).all() if proposition_ids else []
    nodes.extend({"id": str(item.id), "type": "KNOWLEDGE_GAP", "label": item.description, "entityType": item.severity, "aliases": []} for item in gaps)
    edges.extend({"id": f"gap-{item.id}", "source": str(item.id), "target": str(item.proposition_id), "relationship": "GAP_FOR", "stance": item.status, "provenance": item.provenance, "claims": []} for item in gaps)
    return {"nodes": nodes, "edges": edges}


def entity_detail(session: Session, investigation_id: object, entity_id: object) -> dict[str, Any] | None:
    """Return one entity and its source-backed neighborhood in this investigation."""
    entity = session.scalar(
        select(Entity).join(ClaimEntity, ClaimEntity.entity_id == Entity.id)
        .join(Claim, Claim.id == ClaimEntity.claim_id)
        .where(Claim.investigation_id == investigation_id, Entity.id == entity_id).distinct()
    )
    if entity is None:
        return None
    scoped_entity_ids = set(session.scalars(select(ClaimEntity.entity_id).join(Claim, Claim.id == ClaimEntity.claim_id)
        .where(Claim.investigation_id == investigation_id).distinct()).all())
    relationships = session.scalars(select(Relationship).where(
        Relationship.investigation_id == investigation_id,
        or_(Relationship.subject_entity_id == entity.id, Relationship.object_entity_id == entity.id),
    ).order_by(Relationship.predicate, Relationship.id)).all()
    relation_data = []
    for relationship in relationships:
        if relationship.subject_entity_id not in scoped_entity_ids or relationship.object_entity_id not in scoped_entity_ids:
            continue
        subject = session.get(Entity, relationship.subject_entity_id)
        target = session.get(Entity, relationship.object_entity_id)
        claims = session.scalars(select(Claim).join(RelationshipClaim, RelationshipClaim.claim_id == Claim.id)
            .where(RelationshipClaim.relationship_id == relationship.id, Claim.investigation_id == investigation_id)
            .order_by(Claim.id)).all()
        support = []
        for claim in claims:
            evidence = session.scalars(select(Evidence).join(ClaimEvidence, ClaimEvidence.evidence_id == Evidence.id)
                .where(ClaimEvidence.claim_id == claim.id, Evidence.investigation_id == investigation_id)).all()
            paper = session.get(Paper, claim.paper_id)
            support.append({"claimId": str(claim.id), "claim": claim.claim_text,
                "paper": {"id": str(paper.id), "title": paper.title, "source": paper.source,
                    "pmid": paper.pmid, "doi": paper.doi} if paper else None,
                "evidence": [{"id": str(item.id), "text": item.extracted_text,
                    "sourceLocation": item.source_location, "sourceSpan": item.source_span,
                    "polarity": item.polarity, "propositionId": str(item.proposition_id) if item.proposition_id else None}
                    for item in evidence]})
        proposition_id = (relationship.relationship_metadata or {}).get("proposition_id")
        proposition = session.scalar(select(Proposition).where(
            Proposition.investigation_id == investigation_id, Proposition.id == proposition_id,
        )) if proposition_id else None
        relation_data.append({"id": str(relationship.id), "predicate": relationship.predicate,
            "stance": relationship.stance, "confidence": float(relationship.confidence),
            "confidenceMeaning": (relationship.relationship_metadata or {}).get("confidence_semantics"),
            "subject": {"id": str(subject.id), "label": subject.canonical_name, "type": subject.entity_type} if subject else None,
            "object": {"id": str(target.id), "label": target.canonical_name, "type": target.entity_type} if target else None,
            "proposition": {"id": str(proposition.id), "description": proposition.description, "provenance": proposition.provenance} if proposition else None,
            "support": support})
    claims = session.scalars(select(Claim).join(ClaimEntity, ClaimEntity.claim_id == Claim.id)
        .where(ClaimEntity.entity_id == entity.id, Claim.investigation_id == investigation_id).distinct().order_by(Claim.id)).all()
    propositions = session.scalars(select(Proposition).join(Claim, Claim.proposition_id == Proposition.id)
        .join(ClaimEntity, ClaimEntity.claim_id == Claim.id)
        .where(ClaimEntity.entity_id == entity.id, Proposition.investigation_id == investigation_id).distinct()).all()
    hypotheses = session.scalars(select(Hypothesis).where(Hypothesis.investigation_id == investigation_id,
        Hypothesis.proposition_id.in_([item.id for item in propositions])).order_by(Hypothesis.id)).all() if propositions else []
    snapshots = session.scalars(select(ResearchSnapshot).where(ResearchSnapshot.investigation_id == investigation_id)
        .order_by(ResearchSnapshot.snapshot_number)).all()
    snapshot_provenance = []
    for snapshot in snapshots:
        if any(str(row.get("id")) == str(entity.id) for row in (snapshot.manifest or {}).get("entities", [])):
            run = session.get(InvestigationRun, snapshot.run_id)
            snapshot_provenance.append({"snapshotId": str(snapshot.id), "snapshotNumber": snapshot.snapshot_number,
                "manifestDigest": snapshot.manifest_digest, "runId": str(snapshot.run_id),
                "runNumber": run.run_number if run else None})
    return {"id": str(entity.id), "canonicalName": entity.canonical_name, "normalizedName": entity.normalized_name,
        "entityType": entity.entity_type, "aliases": [],
        "relationships": relation_data,
        "claims": [{"id": str(item.id), "text": item.claim_text, "paperId": str(item.paper_id)} for item in claims],
        "propositions": [{"id": str(item.id), "description": item.description, "provenance": item.provenance} for item in propositions],
        "hypotheses": [{"id": str(item.id), "statement": item.statement, "status": item.status,
            "provenance": item.provenance} for item in hypotheses], "snapshots": snapshot_provenance}


def graph_snapshot_diff(left: ResearchSnapshot, right: ResearchSnapshot) -> dict[str, Any]:
    """Compare bounded graph state from two immutable snapshots."""
    if left.investigation_id != right.investigation_id:
        raise ValueError("Snapshots must belong to the same investigation.")
    lm, rm = scoped_snapshot_manifest(left.manifest), scoped_snapshot_manifest(right.manifest)
    def keyed(section: str, key):
        return {key(row): row for row in lm.get(section, [])}, {key(row): row for row in rm.get(section, [])}
    le, re_ = keyed("entities", lambda row: (row.get("entity_type"), row.get("normalized_name")) if row.get("normalized_name") else row["id"])
    lr, rr = keyed("relationships", lambda row: (str(row.get("subject_entity_id")), row.get("predicate"), str(row.get("object_entity_id"))))
    def delta(before, after):
        return {"added": [after[k] for k in sorted(after.keys() - before.keys(), key=str)],
            "removed": [before[k] for k in sorted(before.keys() - after.keys(), key=str)],
            "changed": [{"before": before[k], "after": after[k]} for k in sorted(before.keys() & after.keys(), key=str)
                if before[k].get("stance") != after[k].get("stance") or before[k].get("claim_ids", []) != after[k].get("claim_ids", [])
                or before[k].get("confidence") != after[k].get("confidence")]}
    return {"leftSnapshotId": str(left.id), "rightSnapshotId": str(right.id),
        "entities": delta(le, re_), "relationships": delta(lr, rr)}
