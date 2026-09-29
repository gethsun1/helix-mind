"""Deterministic, investigation-scoped literature contribution summaries."""

from __future__ import annotations

import re
import json
from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Claim, ClaimEntity, ClaimEvidence, Entity, Evidence, Hypothesis, InvestigationPaper,
    Paper, Proposition, Relationship, RelationshipClaim,
)

FORMULA_VERSION = "literature-relevance-v1"
RELEVANCE_WEIGHTS = {"retrieval_rank": .15, "evidence_contribution": .30, "entity_overlap": .20, "proposition_linkage": .20, "hypothesis_linkage": .15}


def calculate_relevance(*, rank: int | None, evidence_count: int, entity_count: int, has_proposition: bool, has_hypothesis: bool) -> dict[str, Any]:
    rank_signal = min(1.0, max(0.0, 1.0 - ((rank - 1) / 20.0))) if rank is not None and rank >= 1 else 0.0
    inputs = {
        "retrieval_rank": rank_signal,
        "evidence_contribution": min(1.0, max(0, evidence_count) / 3.0),
        "entity_overlap": min(1.0, max(0, entity_count) / 3.0),
        "proposition_linkage": 1.0 if has_proposition else 0.0,
        "hypothesis_linkage": 1.0 if has_hypothesis else 0.0,
    }
    return {"score": round(sum(inputs[key] * RELEVANCE_WEIGHTS[key] for key in RELEVANCE_WEIGHTS), 4), "formulaVersion": FORMULA_VERSION, "inputs": inputs, "weights": RELEVANCE_WEIGHTS, "meaning": "Deterministic retrieval and investigation-linkage ordering signal; not evidence confidence or scientific truth."}


def normalized_title(title: str) -> str:
    """Conservative exact title key; never used alone to merge records."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", title.casefold())).strip()


def identity_keys(paper: Paper) -> set[str]:
    keys = set()
    for label, value in (("pmid", paper.pmid), ("doi", paper.doi), ("pmcid", paper.pmcid)):
        if value:
            cleaned = value.strip().casefold()
            cleaned = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", cleaned)
            cleaned = re.sub(r"^(pmid:|pmc:)", "", cleaned)
            keys.add(f"{label}:{cleaned}")
    if paper.title and paper.title.strip():
        keys.add(f"title:{normalized_title(paper.title)}")
    return keys


def publication_contribution(session: Session, investigation_id: UUID, paper: Paper, association: InvestigationPaper | None = None) -> dict[str, Any]:
    """Counts and paths use only rows scoped to the requested investigation."""
    claims = session.scalars(select(Claim).where(Claim.investigation_id == investigation_id, Claim.paper_id == paper.id)).all()
    evidence = session.scalars(select(Evidence).where(Evidence.investigation_id == investigation_id, Evidence.paper_id == paper.id)).all()
    entity_ids = set(session.scalars(select(ClaimEntity.entity_id).join(Claim, Claim.id == ClaimEntity.claim_id).join(ClaimEvidence, ClaimEvidence.claim_id == Claim.id).join(Evidence, Evidence.id == ClaimEvidence.evidence_id).where(Claim.investigation_id == investigation_id, Claim.paper_id == paper.id, Evidence.investigation_id == investigation_id, Evidence.paper_id == paper.id)).all())
    entities = session.scalars(select(Entity).where(Entity.id.in_(entity_ids))).all() if entity_ids else []
    relationship_ids = set(session.scalars(select(RelationshipClaim.relationship_id).join(Claim, Claim.id == RelationshipClaim.claim_id).join(ClaimEvidence, ClaimEvidence.claim_id == Claim.id).join(Evidence, Evidence.id == ClaimEvidence.evidence_id).where(Claim.investigation_id == investigation_id, Claim.paper_id == paper.id, Evidence.investigation_id == investigation_id, Evidence.paper_id == paper.id)).all())
    relationships = session.scalars(select(Relationship).where(Relationship.investigation_id == investigation_id, Relationship.id.in_(relationship_ids))).all() if relationship_ids else []
    proposition_ids = {item.proposition_id for item in evidence if item.proposition_id}
    propositions = session.scalars(select(Proposition).where(Proposition.investigation_id == investigation_id, Proposition.id.in_(proposition_ids))).all() if proposition_ids else []
    hypotheses = session.scalars(select(Hypothesis).where(Hypothesis.investigation_id == investigation_id, Hypothesis.proposition_id.in_(proposition_ids))).all() if proposition_ids else []
    polarities = Counter(item.polarity for item in evidence if item.polarity)
    relevance = calculate_relevance(rank=association.rank if association else None, evidence_count=len(evidence), entity_count=len(entity_ids), has_proposition=bool(propositions), has_hypothesis=bool(hypotheses))
    return {
        "publicationId": str(paper.id), "title": paper.title,
        "identifiers": {"pmid": paper.pmid, "pmcid": paper.pmcid, "doi": paper.doi},
        "source": paper.source, "sourceRecords": (paper.paper_metadata or {}).get("source_records", [paper.source]),
        "retrieval": {"query": association.source_query if association else None, "source": association.source if association else None, "searchId": str(association.research_search_id) if association and association.research_search_id else None, "discoveredAt": association.discovered_at if association else None},
        "metadata": {"authors": paper.authors, "journal": paper.journal, "publicationDate": paper.publication_date},
        "counts": {"evidence": len(evidence), "claims": len(claims), "entities": len(entity_ids), "relationships": len(relationships), "propositions": len(propositions), "hypotheses": len(hypotheses)},
        "evidencePolarity": dict(sorted(polarities.items())),
        "relevance": relevance,
        "contributions": {"evidence": [{"id": str(item.id), "text": item.extracted_text, "sourceLocation": item.source_location, "sourceSpan": item.source_span, "polarity": item.polarity} for item in evidence], "claims": [{"id": str(item.id), "text": item.claim_text} for item in claims], "entities": [{"id": str(item.id), "name": item.canonical_name, "type": item.entity_type} for item in entities], "relationships": [{"id": str(item.id), "subjectEntityId": str(item.subject_entity_id), "predicate": item.predicate, "objectEntityId": str(item.object_entity_id), "stance": item.stance, "evidenceIds": sorted(str(value) for value in session.scalars(select(Evidence.id).join(ClaimEvidence, ClaimEvidence.evidence_id == Evidence.id).join(Claim, Claim.id == ClaimEvidence.claim_id).join(RelationshipClaim, RelationshipClaim.claim_id == Claim.id).where(RelationshipClaim.relationship_id == item.id, Claim.investigation_id == investigation_id, Evidence.investigation_id == investigation_id, Evidence.paper_id == paper.id)).all())} for item in relationships], "propositions": [{"id": str(item.id), "text": item.description} for item in propositions], "hypotheses": [{"id": str(item.id), "statement": item.statement, "status": item.status} for item in hypotheses]},
    }


def deduplication_groups(papers: list[Paper]) -> list[dict[str, Any]]:
    """Report identifier-backed duplicates; a title key alone is advisory."""
    groups: dict[str, list[Paper]] = {}
    for paper in papers:
        for key in identity_keys(paper):
            groups.setdefault(key, []).append(paper)
    result = []
    for key, matches in sorted(groups.items()):
        unique = {item.id: item for item in matches}
        if len(unique) > 1:
            result.append({"identityKey": key, "publicationIds": sorted(str(value) for value in unique), "basis": "title_candidate" if key.startswith("title:") else "canonical_identifier", "merged": False})
    return result


def _manifest_contributions(manifest: dict[str, Any]) -> dict[str, dict[str, dict[str, str]]]:
    """Return snapshot-frozen publication-to-record links without live DB reads."""
    papers = {str(row["id"]): row for row in manifest.get("papers", [])}
    names = ("evidence", "claims", "entities", "relationships", "propositions", "hypotheses")
    result = {paper_id: {name: {} for name in names} for paper_id in papers}
    records = {name: {str(row["id"]): row for row in manifest.get(name, [])} for name in names}

    def add(paper_id: str, kind: str, record_id: str) -> None:
        record = records[kind][record_id]
        fingerprint = str(record.get("record_digest") or json.dumps(record, sort_keys=True, ensure_ascii=True, default=str))
        result[paper_id][kind][record_id] = fingerprint

    claims = {str(row["id"]): row for row in manifest.get("claims", [])}
    for claim in claims.values():
        paper_id = str(claim.get("paper_id", ""))
        if paper_id in result:
            add(paper_id, "claims", str(claim["id"]))
            if claim.get("proposition_id"):
                proposition_id = str(claim["proposition_id"])
                if proposition_id in records["propositions"]:
                    add(paper_id, "propositions", proposition_id)
    for evidence in manifest.get("evidence", []):
        paper_id = str(evidence.get("paper_id", ""))
        if paper_id not in result:
            continue
        add(paper_id, "evidence", str(evidence["id"]))
        if evidence.get("proposition_id"):
            proposition_id = str(evidence["proposition_id"])
            if proposition_id in records["propositions"]:
                add(paper_id, "propositions", proposition_id)
    for entity in manifest.get("entities", []):
        for paper_id in (entity.get("metadata") or {}).get("source_papers", []):
            if str(paper_id) in result:
                add(str(paper_id), "entities", str(entity["id"]))
    for relationship in manifest.get("relationships", []):
        for claim_id in relationship.get("claim_ids", []):
            claim = claims.get(str(claim_id))
            if claim is None:
                continue
            paper_id = str(claim.get("paper_id", ""))
            if paper_id in result:
                add(paper_id, "relationships", str(relationship["id"]))
                if claim.get("proposition_id"):
                    proposition_id = str(claim["proposition_id"])
                    if proposition_id in records["propositions"]:
                        add(paper_id, "propositions", proposition_id)
    for hypothesis in manifest.get("hypotheses", []):
        proposition_id = str(hypothesis.get("proposition_id", ""))
        for paper_id, contributions in result.items():
            if proposition_id and proposition_id in contributions["propositions"] and str(hypothesis["id"]) in records["hypotheses"]:
                add(paper_id, "hypotheses", str(hypothesis["id"]))
    return result


def snapshot_literature_diff(left_manifest: dict[str, Any], right_manifest: dict[str, Any]) -> dict[str, Any]:
    left_papers = {str(row["id"]): row for row in left_manifest.get("papers", [])}
    right_papers = {str(row["id"]): row for row in right_manifest.get("papers", [])}
    left_links, right_links = _manifest_contributions(left_manifest), _manifest_contributions(right_manifest)
    left_ids, right_ids = set(left_papers), set(right_papers)
    names = ("evidence", "claims", "entities", "relationships", "propositions", "hypotheses")
    changes = []
    for paper_id in sorted(left_ids & right_ids):
        before, after = left_links[paper_id], right_links[paper_id]
        delta = {name: {"added": sorted(after[name].keys() - before[name].keys()), "removed": sorted(before[name].keys() - after[name].keys()), "changed": sorted(key for key in before[name].keys() & after[name].keys() if before[name][key] != after[name][key])} for name in names if before[name] != after[name]}
        if delta:
            changes.append({"publicationId": paper_id, "title": right_papers[paper_id].get("title"), "changes": delta})
    graph_left = {paper_id for paper_id, links in left_links.items() if links["relationships"]}
    graph_right = {paper_id for paper_id, links in right_links.items() if links["relationships"]}
    return {
        "publicationsAdded": [right_papers[key] for key in sorted(right_ids - left_ids)],
        "publicationsRemoved": [left_papers[key] for key in sorted(left_ids - right_ids)],
        "publicationsRetained": [right_papers[key] for key in sorted(left_ids & right_ids)],
        "contributionChanges": changes,
        "graphLinkedPublications": {"added": sorted(graph_right - graph_left), "removed": sorted(graph_left - graph_right)},
        "provenance": "Differences are derived only from records frozen in the two immutable snapshot manifests.",
    }
