from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.knowledge_extraction import claim_hash
from app.main import app
from app.models import (Claim, ClaimEntity, ClaimEvidence, Entity, Evidence, Investigation,
                        InvestigationPaper, InvestigationRun, Paper, Relationship, ResearchSnapshot,
                        SemanticExtraction, User)
from app.research_reproducibility import create_run, digest_json
from app.semantic_extraction import _parse_output, execute_semantic_extraction, validate_candidate


def _seed():
    with SessionLocal() as session:
        owner = session.scalar(select(User).where(User.role == "USER").order_by(User.id).limit(1))
        assert owner is not None
        investigation = Investigation(owner_id=owner.id, title="M5 synthetic", question="What relation is source grounded?", status="COMPLETED")
        session.add(investigation)
        session.flush()
        paper = Paper(source="PUBMED", external_id=f"m5-{uuid.uuid4()}", title="CRISPR study",
                      abstract="CRISPR is associated with HBB.", authors=["Synthetic"], publication_date=date(2025, 1, 1), pmid=f"m5-{uuid.uuid4()}")
        session.add(paper)
        session.flush()
        session.add(InvestigationPaper(investigation_id=investigation.id, paper_id=paper.id, source="PUBMED", source_query="synthetic"))
        source_text = "CRISPR is associated with HBB."
        claim = Claim(investigation_id=investigation.id, paper_id=paper.id, claim_text=source_text,
                      normalized_text=source_text.lower(), claim_hash=claim_hash(investigation.id, paper.id, source_text))
        session.add(claim)
        evidence = Evidence(investigation_id=investigation.id, paper_id=paper.id, source_location="abstract",
                            source_span={"start": 0, "end": len(source_text)}, evidence_type="ABSTRACT", extracted_text=source_text,
                            strength=0.8, confidence=0.8, extraction_method="deterministic_abstract")
        session.add(evidence)
        crispr = session.scalar(select(Entity).where(Entity.entity_type == "TECHNOLOGY", Entity.normalized_name == "crispr"))
        hbb = session.scalar(select(Entity).where(Entity.entity_type == "GENE", Entity.normalized_name == "hbb"))
        if crispr is None:
            crispr = Entity(entity_type="TECHNOLOGY", canonical_name="CRISPR", normalized_name="crispr")
            session.add(crispr)
        if hbb is None:
            hbb = Entity(entity_type="GENE", canonical_name="HBB", normalized_name="hbb")
            session.add(hbb)
        session.flush()
        session.add_all([ClaimEvidence(claim_id=claim.id, evidence_id=evidence.id),
                         ClaimEntity(claim_id=claim.id, entity_id=crispr.id), ClaimEntity(claim_id=claim.id, entity_id=hbb.id)])
        source_run = create_run(session, investigation, status="COMPLETED")
        source_run.completed_at = source_run.created_at
        session.commit()
        result = (owner.id, investigation.id, paper.id, evidence.id, claim.id, source_run.id)
        return result


def _cleanup(investigation_ids, paper_ids):
    with SessionLocal() as session:
        for item in session.scalars(select(Investigation).where(Investigation.id.in_(investigation_ids))).all():
            session.delete(item)
        session.flush()
        for item in session.scalars(select(Paper).where(Paper.id.in_(paper_ids))).all():
            session.delete(item)
        session.commit()


def _candidate(evidence_id, **updates):
    candidate = {"evidence_id": str(evidence_id), "subject": "CRISPR", "subject_type": "TECHNOLOGY",
                 "predicate": "ASSOCIATED_WITH", "object": "HBB", "object_type": "GENE",
                 "source_span": "CRISPR is associated with HBB.", "semantic_type": "EVIDENCE_RELATION"}
    return {**candidate, **updates}


class FakeRouter:
    def __init__(self, content):
        self.content = content

    def chat(self, *args, **kwargs):
        return SimpleNamespace(provider="synthetic", model="fixture-model", content=self.content, latency_ms=1)


def test_candidate_schema_and_exact_source_span_validation():
    owner_id, investigation_id, paper_id, evidence_id, claim_id, _ = _seed()
    try:
        with SessionLocal() as session:
            investigation = session.get(Investigation, investigation_id)
            evidence = session.get(Evidence, evidence_id)
            paper = session.get(Paper, paper_id)
            claim = session.get(Claim, claim_id)
            assert investigation and evidence and paper and claim
            errors, normalized = validate_candidate(session, investigation, evidence, paper, claim, _candidate(evidence_id))
            assert errors == []
            source_length = len("CRISPR is associated with HBB.")
            assert normalized["source_locator"] == {"source_location": "abstract", "start": 0, "end": source_length, "evidence_start": 0, "evidence_end": source_length}
            invalid, _ = validate_candidate(session, investigation, evidence, paper, claim,
                                            _candidate(evidence_id, source_span="CRISPR causes HBB."))
            assert "source_span_mismatch" in invalid
            invalid_type, _ = validate_candidate(session, investigation, evidence, paper, claim,
                                                 _candidate(evidence_id, semantic_type="ONTOLOGY"))
            assert "unsupported_semantic_type" in invalid_type
            wrong_evidence = _candidate(evidence_id)
            wrong_evidence["evidence_id"] = str(uuid.uuid4())
            invalid_owner, _ = validate_candidate(session, investigation, evidence, paper, claim, wrong_evidence)
            assert "evidence_mismatch" in invalid_owner
            no_provenance, _ = validate_candidate(session, investigation, evidence, paper, None, _candidate(evidence_id))
            assert "claim_ownership_mismatch" in no_provenance
            invalid_relation, _ = validate_candidate(session, investigation, evidence, paper, claim,
                                                     _candidate(evidence_id, predicate="INVENTED_RELATION"))
            assert "unsupported_relation_type" in invalid_relation
            unknown_entity, _ = validate_candidate(session, investigation, evidence, paper, claim,
                                                   _candidate(evidence_id, subject="Unknown entity", subject_type="OTHER"))
            assert "unknown_subject_entity" in unknown_entity
            self_relation, _ = validate_candidate(session, investigation, evidence, paper, claim,
                                                  _candidate(evidence_id, object="CRISPR", object_type="TECHNOLOGY"))
            assert "self_relation" in self_relation
        assert _parse_output('{"relations": []}') == []
        try:
            _parse_output('{"relations": [], "extra": true}')
            assert False, "unknown response key should fail closed"
        except ValueError:
            pass
    finally:
        _cleanup([investigation_id], [paper_id])


def test_only_validated_candidates_project_and_hash_deduplicates():
    _, investigation_id, paper_id, evidence_id, claim_id, source_run_id = _seed()
    output = {"relations": [_candidate(evidence_id), _candidate(evidence_id, source_span="unsupported span") ]}
    with SessionLocal() as session:
        investigation = session.get(Investigation, investigation_id)
        source_run = session.get(InvestigationRun, source_run_id)
        assert investigation and source_run
        snapshot_manifest = {
            "sentinel": "immutable",
            "evidence": [{"id": str(evidence_id)}],
            "claims": [{"id": str(claim_id)}],
            "entities": [{"id": str(item)} for item in session.scalars(select(Entity.id).join(ClaimEntity, ClaimEntity.entity_id == Entity.id).join(Claim, Claim.id == ClaimEntity.claim_id).where(Claim.investigation_id == investigation_id)).all()],
            "papers": [{"id": str(paper_id), "abstract": "CRISPR is associated with HBB."}],
        }
        snapshot = ResearchSnapshot(investigation_id=investigation_id, run_id=source_run_id,
                                    snapshot_number=1, manifest=snapshot_manifest,
                                    manifest_digest=digest_json(snapshot_manifest))
        session.add(snapshot)
        session.commit()
        snapshot_id = snapshot.id
        original_snapshot_digest = snapshot.manifest_digest
        result = execute_semantic_extraction(session, investigation, source_run, router=FakeRouter(__import__("json").dumps(output)))
        assert result["validCount"] == 1
        assert result["rejectedCount"] == 1
        assert result["projectedCount"] == 1
        extraction_run = session.get(InvestigationRun, uuid.UUID(result["extractionRunId"]))
        assert extraction_run and extraction_run.parent_run_id == source_run_id
        assert extraction_run.input_manifest["evidence_ids"] == [str(evidence_id)]
        assert extraction_run.input_manifest["publication_ids"] == [str(paper_id)]
        assert extraction_run.input_manifest["evidence_limit"] == 20
        assert extraction_run.provider_metadata["provider"] == "synthetic"
        assert extraction_run.provider_metadata["model"] == "fixture-model"
        assert extraction_run.provider_metadata["output_extraction_ids"]
        rows = session.scalars(select(SemanticExtraction).where(SemanticExtraction.investigation_id == investigation_id)).all()
        assert sorted(row.validation_status for row in rows) == ["REJECTED", "VALID"]
        assert session.scalar(select(func.count(Relationship.id)).where(Relationship.investigation_id == investigation_id)) == 1
        projected = session.scalar(select(Relationship).where(Relationship.investigation_id == investigation_id))
        assert projected and projected.confidence == 0 and projected.strength == 0
        frozen = session.get(ResearchSnapshot, snapshot_id)
        assert frozen and frozen.manifest == snapshot_manifest
        assert frozen.manifest_digest == original_snapshot_digest == digest_json(frozen.manifest)
        # Repeating identical output for the same source run leaves canonical candidate rows and graph edges unchanged.
        execute_semantic_extraction(session, investigation, source_run, router=FakeRouter(__import__("json").dumps(output)))
        assert session.scalar(select(func.count(SemanticExtraction.id)).where(SemanticExtraction.investigation_id == investigation_id)) == 2
        assert session.scalar(select(func.count(Relationship.id)).where(Relationship.investigation_id == investigation_id)) == 1
    _cleanup([investigation_id], [paper_id])


def test_semantic_extraction_api_is_investigation_scoped():
    owner_id, investigation_id, paper_id, _, _, _ = _seed()
    from app.security import get_current_user
    with SessionLocal() as session:
        owner = session.get(User, owner_id)
        assert owner is not None
        test_user = SimpleNamespace(id=owner_id, role=owner.role)
        app.dependency_overrides[get_current_user] = lambda: test_user
        other = Investigation(owner_id=owner_id, title="Other investigation", question="isolated?")
        other_owner = session.scalar(select(User).where(User.id != owner_id, User.role == "USER").limit(1))
        created_owner = other_owner is None
        if other_owner is None:
            other_owner = User(email=f"m5-isolation-{uuid.uuid4()}@example.invalid", role="USER")
            session.add(other_owner)
            session.flush()
        foreign = Investigation(owner_id=other_owner.id, title="Foreign investigation", question="isolated across owners?")
        session.add_all([other, foreign])
        session.commit()
        other_id, foreign_id, other_owner_id = other.id, foreign.id, other_owner.id
    try:
        response = TestClient(app).get(f"/api/v1/investigations/{other_id}/literature/semantic-extractions")
        assert response.status_code == 200 and response.json()["extractions"] == []
        denied = TestClient(app).get(f"/api/v1/investigations/{foreign_id}/literature/semantic-extractions")
        assert denied.status_code == 404
    finally:
        app.dependency_overrides.clear()
        _cleanup([investigation_id, other_id, foreign_id], [paper_id])
        if created_owner:
            with SessionLocal() as session:
                other_owner = session.get(User, other_owner_id)
                if other_owner:
                    session.delete(other_owner)
                    session.commit()
