from __future__ import annotations

from collections import Counter
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.db import SessionLocal
from app.literature_intelligence import deduplication_groups, publication_contribution, snapshot_literature_diff
from app.models import Claim, ClaimEntity, ClaimEvidence, Evidence, Entity, Hypothesis, Investigation, InvestigationPaper, Paper, Proposition, Relationship, RelationshipClaim, ResearchSnapshot, User
from app.security import get_current_user

router = APIRouter(prefix="/api/v1/investigations", tags=["literature intelligence"])


def _scope(session, investigation_id: UUID, user: User) -> Investigation:
    query = select(Investigation).where(Investigation.id == investigation_id)
    if user.role != "ADMIN":
        query = query.where(Investigation.owner_id == user.id)
    row = session.scalar(query)
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return row


@router.get("/{investigation_id}/literature/intelligence")
def literature_intelligence(investigation_id: UUID, user: User = Depends(get_current_user)) -> dict:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        rows = session.execute(select(Paper, InvestigationPaper).join(InvestigationPaper, InvestigationPaper.paper_id == Paper.id).where(InvestigationPaper.investigation_id == investigation_id).order_by(InvestigationPaper.rank.asc().nullslast(), Paper.title.asc(), Paper.id.asc())).all()
        publications = [publication_contribution(session, investigation_id, paper, association) for paper, association in rows]
        evidence = session.scalars(select(Evidence).where(Evidence.investigation_id == investigation_id)).all()
        sources = Counter(source for paper, association in rows for source in ((paper.paper_metadata or {}).get("source_records") or [association.source or paper.source]))
        years = Counter(str(paper.publication_date.year) if paper.publication_date else "undated" for paper, _ in rows)
        entity_support: dict[str, set[str]] = {}
        proposition_support: dict[str, set[str]] = {}
        hypothesis_support: dict[str, set[str]] = {}
        for item in publications:
            paper_id = item["publicationId"]
            for key, target in (("entities", entity_support), ("propositions", proposition_support), ("hypotheses", hypothesis_support)):
                for record in item["contributions"][key]:
                    target.setdefault(record.get("id", record.get("entityId", "")), set()).add(paper_id)
        coverage = {
            "entityPublicationSupport": [{"entityId": key, "publicationCount": len(value), "coverage": "multiple retrieved publications" if len(value) >= 3 else "limited retrieved evidence"} for key, value in sorted(entity_support.items())],
            "propositionPublicationSupport": [{"propositionId": key, "publicationCount": len(value), "coverage": "limited retrieved evidence" if len(value) < 2 else "multiple retrieved publications"} for key, value in sorted(proposition_support.items())],
            "hypothesisPublicationSupport": [{"hypothesisId": key, "publicationCount": len(value), "coverage": "limited retrieved evidence" if len(value) < 2 else "multiple retrieved publications"} for key, value in sorted(hypothesis_support.items())],
            "note": "Coverage counts persisted publication links; limited retrieved evidence does not imply evidence of absence.",
        }
        return {"investigationId": str(investigation_id), "formulaVersion": "literature-relevance-v1", "publications": publications, "deduplicationCandidates": deduplication_groups([paper for paper, _ in rows]), "coverage": coverage, "landscape": {"retrievedPublications": len(rows), "totalPublications": len(rows), "uniquePublications": len({paper.id for paper, _ in rows}), "evidenceBearingPublications": sum(item["counts"]["evidence"] > 0 for item in publications), "entityLinkedPublications": sum(item["counts"]["entities"] > 0 for item in publications), "relationshipLinkedPublications": sum(item["counts"]["relationships"] > 0 for item in publications), "graphContributingPublications": sum(item["counts"]["relationships"] > 0 for item in publications), "propositionLinkedPublications": sum(item["counts"]["propositions"] > 0 for item in publications), "propositionContributingPublications": sum(item["counts"]["propositions"] > 0 for item in publications), "hypothesisLinkedPublications": sum(item["counts"]["hypotheses"] > 0 for item in publications), "hypothesisContributingPublications": sum(item["counts"]["hypotheses"] > 0 for item in publications), "sourceDistribution": dict(sorted(sources.items())), "publicationDateDistribution": dict(sorted(years.items())), "evidencePolarity": dict(sorted(Counter(item.polarity for item in evidence if item.polarity).items()))}, "semantics": "Counts and paths reflect persisted investigation-scoped evidence and graph links. Limited retrieved evidence does not establish evidence of absence."}


@router.get("/{investigation_id}/literature/publications/{paper_id}")
def literature_publication(investigation_id: UUID, paper_id: UUID, user: User = Depends(get_current_user)) -> dict:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        row = session.execute(select(Paper, InvestigationPaper).join(InvestigationPaper, InvestigationPaper.paper_id == Paper.id).where(InvestigationPaper.investigation_id == investigation_id, Paper.id == paper_id)).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Publication not found in this investigation.")
        return publication_contribution(session, investigation_id, row[0], row[1])


@router.get("/{investigation_id}/literature/publications/{paper_id}/graph")
def publication_graph(investigation_id: UUID, paper_id: UUID, user: User = Depends(get_current_user)) -> dict:
    return literature_publication(investigation_id, paper_id, user)


@router.get("/{investigation_id}/literature/graph/{kind}/{record_id}/publications")
def graph_supporting_publications(investigation_id: UUID, kind: str, record_id: UUID, user: User = Depends(get_current_user)) -> dict:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        kind = kind.casefold()
        if kind == "entity":
            target = session.scalar(select(Entity.id).join(ClaimEntity, ClaimEntity.entity_id == Entity.id).join(Claim, Claim.id == ClaimEntity.claim_id).where(Entity.id == record_id, Claim.investigation_id == investigation_id))
            paper_ids = select(Evidence.paper_id).join(ClaimEvidence, ClaimEvidence.evidence_id == Evidence.id).join(Claim, Claim.id == ClaimEvidence.claim_id).join(ClaimEntity, ClaimEntity.claim_id == Claim.id).where(Claim.investigation_id == investigation_id, Evidence.investigation_id == investigation_id, ClaimEntity.entity_id == record_id, Evidence.paper_id.is_not(None))
        elif kind == "relationship":
            target = session.scalar(select(Relationship.id).where(Relationship.id == record_id, Relationship.investigation_id == investigation_id))
            paper_ids = select(Claim.paper_id).join(RelationshipClaim, RelationshipClaim.claim_id == Claim.id).join(ClaimEvidence, ClaimEvidence.claim_id == Claim.id).join(Evidence, Evidence.id == ClaimEvidence.evidence_id).where(Claim.investigation_id == investigation_id, RelationshipClaim.relationship_id == record_id, Evidence.investigation_id == investigation_id)
        elif kind == "proposition":
            target = session.scalar(select(Proposition.id).where(Proposition.id == record_id, Proposition.investigation_id == investigation_id))
            paper_ids = select(Evidence.paper_id).where(Evidence.investigation_id == investigation_id, Evidence.proposition_id == record_id, Evidence.paper_id.is_not(None))
        elif kind == "hypothesis":
            hypothesis = session.scalar(select(Hypothesis).where(Hypothesis.id == record_id, Hypothesis.investigation_id == investigation_id))
            target = hypothesis.id if hypothesis else None
            paper_ids = select(Evidence.paper_id).where(Evidence.investigation_id == investigation_id, Evidence.proposition_id == (hypothesis.proposition_id if hypothesis else None), Evidence.paper_id.is_not(None))
        else:
            raise HTTPException(status_code=404, detail="Graph record not found.")
        if target is None:
            raise HTTPException(status_code=404, detail="Graph record not found in this investigation.")
        rows = session.execute(select(Paper, InvestigationPaper).join(InvestigationPaper, InvestigationPaper.paper_id == Paper.id).where(InvestigationPaper.investigation_id == investigation_id, Paper.id.in_(paper_ids)).order_by(Paper.title.asc(), Paper.id.asc())).all()
        publications = [publication_contribution(session, investigation_id, paper, association) for paper, association in rows]
        return {"investigationId": str(investigation_id), "kind": kind, "recordId": str(record_id), "publications": publications, "provenance": "Each publication is linked through investigation-scoped claims and persisted evidence."}


@router.get("/{investigation_id}/literature/compare")
def compare_literature(investigation_id: UUID, left_snapshot_id: UUID = Query(alias="leftSnapshotId"), right_snapshot_id: UUID = Query(alias="rightSnapshotId"), user: User = Depends(get_current_user)) -> dict:
    with SessionLocal() as session:
        _scope(session, investigation_id, user)
        left = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.id == left_snapshot_id, ResearchSnapshot.investigation_id == investigation_id))
        right = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.id == right_snapshot_id, ResearchSnapshot.investigation_id == investigation_id))
        if left is None or right is None:
            raise HTTPException(status_code=404, detail="Snapshot not found.")
        return {"leftSnapshotId": str(left.id), "rightSnapshotId": str(right.id), **snapshot_literature_diff(left.manifest, right.manifest)}
