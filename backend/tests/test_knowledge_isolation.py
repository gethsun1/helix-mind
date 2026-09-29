"""Database-backed synthetic fixtures for graph scope boundaries.

These records are test-only fixtures, not scientific evidence.
"""

import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.knowledge_metta import render_investigation_metta
from app.models import (
    Claim, ClaimEntity, ClaimEvidence, Entity, Evidence, Hypothesis, Investigation,
    InvestigationPaper, Paper, Proposition, Relationship, RelationshipClaim,
    ResearchSnapshot, User,
)
from app.research_reproducibility import create_run, digest_json, freeze_snapshot
from app.main import app


def test_same_owner_graph_routes_and_projections_are_investigation_scoped(monkeypatch):
    secret = "m3-investigation-isolation-test-secret"
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", secret)
    get_settings.cache_clear()
    owner_id, other_owner_id = uuid.uuid4(), uuid.uuid4()
    investigation_a_id, investigation_b_id, investigation_other_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    paper_a_id, paper_b_id = uuid.uuid4(), uuid.uuid4()
    shared_id, private_a_id, target_b_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    removed_b_entity_id, added_b_entity_id = uuid.uuid4(), uuid.uuid4()
    claim_a_id, claim_b_id, claim_b2_id, claim_shared_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    evidence_a_id, evidence_b_id, evidence_b2_id, evidence_shared_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    proposition_a_id, proposition_b_id = uuid.uuid4(), uuid.uuid4()
    relation_a_id, relation_b_id = uuid.uuid4(), uuid.uuid4()
    hypothesis_a_id, hypothesis_b_id = uuid.uuid4(), uuid.uuid4()
    snapshot_a_id = snapshot_b_id = snapshot_b2_id = run_a_id = run_b_id = run_b2_id = None
    snapshot_a_digest = snapshot_b_digest = None
    snapshot_b2_digest = None

    with SessionLocal() as session:
        owner = User(id=owner_id, email=f"m3-owner-{owner_id}@example.invalid", role="USER")
        other_owner = User(id=other_owner_id, email=f"m3-other-{other_owner_id}@example.invalid", role="USER")
        session.add_all([owner, other_owner])
        session.flush()
        session.add_all([
            Investigation(id=investigation_a_id, owner_id=owner_id, title="Synthetic A", question="Fixture A", status="COMPLETED"),
            Investigation(id=investigation_b_id, owner_id=owner_id, title="Synthetic B", question="Fixture B", status="COMPLETED"),
            Investigation(id=investigation_other_id, owner_id=other_owner_id, title="Synthetic other owner", question="Fixture C", status="COMPLETED"),
            Paper(id=paper_a_id, source="PUBMED", external_id=f"m3-a-{paper_a_id}", title="Synthetic publication A", abstract="Fixture evidence A.", pmid=f"m3a{str(paper_a_id)[:8]}"),
            Paper(id=paper_b_id, source="EUROPE_PMC", external_id=f"m3-b-{paper_b_id}", title="Synthetic publication B", abstract="Fixture evidence B.", pmid=f"m3b{str(paper_b_id)[:8]}"),
        ])
        session.flush()
        session.add_all([
            Entity(id=shared_id, entity_type="GENE", canonical_name="Shared fixture entity", normalized_name="shared fixture entity", aliases=["A-only alias"], entity_metadata={"source_papers": [str(paper_a_id)], "source_providers": ["PUBMED"]}),
            Entity(id=private_a_id, entity_type="DISEASE", canonical_name="A-only fixture disease", normalized_name="a only fixture disease"),
            Entity(id=target_b_id, entity_type="DISEASE", canonical_name="B-only fixture disease", normalized_name="b only fixture disease"),
            Entity(id=removed_b_entity_id, entity_type="CONCEPT", canonical_name="Removed fixture entity", normalized_name="removed fixture entity"),
            Proposition(id=proposition_a_id, investigation_id=investigation_a_id, subject="Shared fixture entity", predicate="ASSOCIATED_WITH", object="A-only fixture disease", normalized_subject="shared fixture entity", normalized_predicate="associated with", normalized_object="a only fixture disease", proposition_key=f"m3-{proposition_a_id}", description="Fixture A proposition", provenance={"fixture": "synthetic-A"}),
            Proposition(id=proposition_b_id, investigation_id=investigation_b_id, subject="Shared fixture entity", predicate="TARGETS", object="B-only fixture disease", normalized_subject="shared fixture entity", normalized_predicate="targets", normalized_object="b only fixture disease", proposition_key=f"m3-{proposition_b_id}", description="Fixture B proposition", provenance={"fixture": "synthetic-B"}),
        ])
        session.flush()
        session.add_all([
            Claim(id=claim_a_id, investigation_id=investigation_a_id, paper_id=paper_a_id, proposition_id=proposition_a_id, claim_text="Fixture evidence A.", normalized_text="fixture evidence a.", claim_hash=str(claim_a_id), extraction_method="test_fixture", claim_metadata={"fixture": "synthetic-A"}),
            Claim(id=claim_b_id, investigation_id=investigation_b_id, paper_id=paper_b_id, proposition_id=proposition_b_id, claim_text="Fixture evidence B.", normalized_text="fixture evidence b.", claim_hash=str(claim_b_id), extraction_method="test_fixture", claim_metadata={"fixture": "synthetic-B"}),
            Claim(id=claim_shared_id, investigation_id=investigation_b_id, paper_id=paper_a_id, proposition_id=proposition_b_id, claim_text="Investigation B contribution to shared publication.", normalized_text="investigation b contribution to shared publication.", claim_hash=str(claim_shared_id), extraction_method="test_fixture", claim_metadata={"fixture": "synthetic-B-shared-publication"}),
            Evidence(id=evidence_a_id, investigation_id=investigation_a_id, paper_id=paper_a_id, proposition_id=proposition_a_id, source_location="abstract", source_span={"start": 0, "end": 19}, evidence_type="ABSTRACT", extracted_text="Fixture evidence A.", strength=0.6, confidence=0.99, polarity="SUPPORTS", extraction_method="test_fixture"),
            Evidence(id=evidence_b_id, investigation_id=investigation_b_id, paper_id=paper_b_id, proposition_id=proposition_b_id, source_location="abstract", source_span={"start": 0, "end": 19}, evidence_type="ABSTRACT", extracted_text="Fixture evidence B.", strength=0.6, confidence=0.99, polarity="SUPPORTS", extraction_method="test_fixture"),
            Evidence(id=evidence_shared_id, investigation_id=investigation_b_id, paper_id=paper_a_id, proposition_id=proposition_b_id, source_location="synthetic_fixture", source_span=None, evidence_type="ABSTRACT", extracted_text="Investigation B contribution to shared publication.", strength=0.6, confidence=0.99, polarity="SUPPORTS", extraction_method="test_fixture"),
            Relationship(id=relation_a_id, investigation_id=investigation_a_id, subject_entity_id=shared_id, predicate="ASSOCIATED_WITH", object_entity_id=private_a_id, strength=0.6, confidence=0.99, source_type="TEST_FIXTURE", stance="SUPPORTS", relationship_metadata={"proposition_id": str(proposition_a_id), "fixture": "synthetic-A"}),
            Relationship(id=relation_b_id, investigation_id=investigation_b_id, subject_entity_id=shared_id, predicate="TARGETS", object_entity_id=target_b_id, strength=0.6, confidence=0.99, source_type="TEST_FIXTURE", stance="SUPPORTS", relationship_metadata={"proposition_id": str(proposition_b_id), "fixture": "synthetic-B"}),
            Hypothesis(id=hypothesis_a_id, investigation_id=investigation_a_id, proposition_id=proposition_a_id, statement="Fixture A hypothesis", strength=0.6, confidence=0.6, status="active", provenance={"fixture": "synthetic-A"}),
            Hypothesis(id=hypothesis_b_id, investigation_id=investigation_b_id, proposition_id=proposition_b_id, statement="Fixture B hypothesis", strength=0.6, confidence=0.6, status="active", provenance={"fixture": "synthetic-B"}),
            InvestigationPaper(investigation_id=investigation_a_id, paper_id=paper_a_id, source_query="synthetic fixture A", source="PUBMED"),
            InvestigationPaper(investigation_id=investigation_b_id, paper_id=paper_b_id, source_query="synthetic fixture B", source="EUROPE_PMC"),
            InvestigationPaper(investigation_id=investigation_b_id, paper_id=paper_a_id, source_query="synthetic fixture B shared canonical paper", source="PUBMED"),
        ])
        session.flush()
        session.add_all([
            ClaimEntity(claim_id=claim_a_id, entity_id=shared_id, role="SUBJECT"),
            ClaimEntity(claim_id=claim_a_id, entity_id=private_a_id, role="OBJECT"),
            ClaimEntity(claim_id=claim_b_id, entity_id=shared_id, role="SUBJECT"),
            ClaimEntity(claim_id=claim_shared_id, entity_id=shared_id, role="SUBJECT"),
            ClaimEntity(claim_id=claim_b_id, entity_id=target_b_id, role="OBJECT"),
            ClaimEntity(claim_id=claim_b_id, entity_id=removed_b_entity_id, role="MENTIONS"),
            ClaimEvidence(claim_id=claim_a_id, evidence_id=evidence_a_id, role="DIRECT"),
            ClaimEvidence(claim_id=claim_b_id, evidence_id=evidence_b_id, role="DIRECT"),
            ClaimEvidence(claim_id=claim_shared_id, evidence_id=evidence_shared_id, role="DIRECT"),
            RelationshipClaim(relationship_id=relation_a_id, claim_id=claim_a_id),
            RelationshipClaim(relationship_id=relation_b_id, claim_id=claim_b_id),
        ])
        session.flush()
        run_a = create_run(session, session.get(Investigation, investigation_a_id), status="COMPLETED")
        run_b = create_run(session, session.get(Investigation, investigation_b_id), status="COMPLETED")
        snapshot_a = freeze_snapshot(session, session.get(Investigation, investigation_a_id), run_a)
        snapshot_b = freeze_snapshot(session, session.get(Investigation, investigation_b_id), run_b)
        snapshot_a_id, snapshot_b_id = snapshot_a.id, snapshot_b.id
        run_a_id, run_b_id = run_a.id, run_b.id
        snapshot_a_digest = snapshot_a.manifest_digest
        # Reproduce the legacy M2 shape where globally accumulated entity
        # aliases and source paper IDs were copied into a scoped snapshot.
        legacy_manifest = dict(snapshot_b.manifest)
        legacy_entities = [dict(row) for row in legacy_manifest["entities"]]
        legacy_shared = next(row for row in legacy_entities if row["id"] == str(shared_id))
        legacy_shared["aliases"] = ["A-only alias"]
        legacy_shared["metadata"] = {"source_papers": [str(paper_a_id), str(paper_b_id)], "source_providers": ["PUBMED", "EUROPE_PMC"]}
        legacy_manifest["entities"] = legacy_entities
        snapshot_b.manifest = legacy_manifest
        snapshot_b.manifest_digest = digest_json(legacy_manifest)
        snapshot_b_digest = snapshot_b.manifest_digest
        removed_link = session.scalar(select(ClaimEntity).where(ClaimEntity.claim_id == claim_b_id, ClaimEntity.entity_id == removed_b_entity_id))
        session.delete(removed_link)
        session.add(Entity(id=added_b_entity_id, entity_type="CONCEPT", canonical_name="Added fixture entity", normalized_name="added fixture entity"))
        session.flush()
        session.add(Claim(id=claim_b2_id, investigation_id=investigation_b_id, paper_id=paper_b_id, proposition_id=proposition_b_id, claim_text="Fixture second support B.", normalized_text="fixture second support b.", claim_hash=str(claim_b2_id), extraction_method="test_fixture", claim_metadata={"fixture": "synthetic-B"}))
        session.add(Evidence(id=evidence_b2_id, investigation_id=investigation_b_id, paper_id=paper_b_id, proposition_id=proposition_b_id, source_location="abstract", source_span={"start": 0, "end": 19}, evidence_type="ABSTRACT", extracted_text="Fixture second support B.", strength=0.6, confidence=0.8, polarity="CONTRADICTS", extraction_method="test_fixture"))
        session.flush()
        session.add_all([
            ClaimEntity(claim_id=claim_b_id, entity_id=added_b_entity_id, role="MENTIONS"),
            ClaimEntity(claim_id=claim_b2_id, entity_id=shared_id, role="SUBJECT"),
            ClaimEntity(claim_id=claim_b2_id, entity_id=target_b_id, role="OBJECT"),
            ClaimEvidence(claim_id=claim_b2_id, evidence_id=evidence_b2_id, role="DIRECT"),
            RelationshipClaim(relationship_id=relation_b_id, claim_id=claim_b2_id),
        ])
        relation_b = session.get(Relationship, relation_b_id)
        relation_b.stance = "CONTRADICTS"
        relation_b.confidence = 0.8
        session.flush()
        run_b2 = create_run(session, session.get(Investigation, investigation_b_id), parent_run_id=run_b.id, status="COMPLETED")
        snapshot_b2 = freeze_snapshot(session, session.get(Investigation, investigation_b_id), run_b2)
        snapshot_b2_id, run_b2_id, snapshot_b2_digest = snapshot_b2.id, run_b2.id, snapshot_b2.manifest_digest
        metta_a = render_investigation_metta(session, investigation_a_id)
        metta_b = render_investigation_metta(session, investigation_b_id)
        metta_b_repeat = render_investigation_metta(session, investigation_b_id)
        session.commit()

    def bearer(user_id):
        return {"Authorization": f"Bearer {jwt.encode({'sub': str(user_id)}, secret, algorithm='HS256')}"}

    client = TestClient(app)
    base_b = f"/api/v1/investigations/{investigation_b_id}"
    headers_owner = bearer(owner_id)
    headers_other = bearer(other_owner_id)
    try:
        graph = client.get(f"{base_b}/knowledge/graph", headers=headers_owner)
        assert graph.status_code == 200
        graph_text = graph.text
        assert "B-only fixture disease" in graph_text
        assert "A-only fixture disease" not in graph_text
        assert str(relation_b_id) in graph_text and str(relation_a_id) not in graph_text

        detail = client.get(f"{base_b}/knowledge/entities/{shared_id}", headers=headers_owner)
        assert detail.status_code == 200
        assert detail.json()["aliases"] == []
        assert [row["id"] for row in detail.json()["relationships"]] == [str(relation_b_id)]
        detail_text = detail.text
        for forbidden in ("A-only alias", "Fixture evidence A.", str(evidence_a_id), str(proposition_a_id), str(hypothesis_a_id), str(snapshot_a_id)):
            assert forbidden not in detail_text
        for expected in ("Fixture evidence B.", "Fixture second support B.", "Synthetic publication B", "Fixture B proposition", "Fixture B hypothesis", str(snapshot_b2_id)):
            assert expected in detail_text
        assert client.get(f"{base_b}/knowledge/entities/{private_a_id}", headers=headers_owner).status_code == 404
        assert client.get(f"{base_b}/knowledge/entities/{uuid.uuid4()}", headers=headers_owner).status_code == 404
        entity_list = client.get(f"{base_b}/knowledge/entities", headers=headers_owner)
        assert entity_list.status_code == 200
        assert "A-only alias" not in entity_list.text
        assert all(row["aliases"] == [] for row in entity_list.json())

        literature = client.get(f"{base_b}/literature/intelligence", headers=headers_owner)
        assert literature.status_code == 200
        literature_data = literature.json()
        assert literature_data["landscape"]["retrievedPublications"] == 2
        assert literature_data["landscape"]["evidenceBearingPublications"] == 2
        assert literature_data["landscape"]["entityLinkedPublications"] == 2
        assert literature_data["landscape"]["propositionLinkedPublications"] == 2
        assert literature_data["landscape"]["hypothesisLinkedPublications"] == 2
        assert "Synthetic publication A" in literature.text and "Fixture evidence A." not in literature.text
        publication_b = client.get(f"{base_b}/literature/publications/{paper_b_id}", headers=headers_owner)
        assert publication_b.status_code == 200
        assert publication_b.json()["contributions"]["evidence"][0]["sourceSpan"] == {"start": 0, "end": 19}
        assert "Fixture evidence A." not in publication_b.text
        shared_publication_b = client.get(f"{base_b}/literature/publications/{paper_a_id}", headers=headers_owner)
        assert shared_publication_b.status_code == 200
        assert "Investigation B contribution to shared publication." in shared_publication_b.text
        assert "Fixture evidence A." not in shared_publication_b.text
        shared_publication_a = client.get(f"/api/v1/investigations/{investigation_a_id}/literature/publications/{paper_a_id}", headers=headers_owner)
        assert shared_publication_a.status_code == 200
        assert "Fixture evidence A." in shared_publication_a.text
        assert "Investigation B contribution to shared publication." not in shared_publication_a.text
        assert client.get(f"{base_b}/literature/intelligence", headers=headers_other).status_code == 404
        assert client.get(f"/api/v1/investigations/{investigation_a_id}/literature/publications/{paper_a_id}", headers=headers_other).status_code == 404

        for kind, record_id in (("entity", shared_id), ("relationship", relation_b_id), ("proposition", proposition_b_id), ("hypothesis", hypothesis_b_id)):
            response = client.get(f"{base_b}/literature/graph/{kind}/{record_id}/publications", headers=headers_owner)
            assert response.status_code == 200
            expected_ids = {str(paper_b_id)} if kind == "relationship" else {str(paper_a_id), str(paper_b_id)}
            assert {row["publicationId"] for row in response.json()["publications"]} == expected_ids
            assert "Fixture evidence B." in response.text
            assert "Fixture evidence A." not in response.text
        assert client.get(f"{base_b}/literature/graph/entity/{private_a_id}/publications", headers=headers_owner).status_code == 404
        assert client.get(f"{base_b}/literature/graph/entity/{shared_id}/publications", headers=headers_other).status_code == 404

        literature_diff = client.get(f"{base_b}/literature/compare?leftSnapshotId={snapshot_b_id}&rightSnapshotId={snapshot_b2_id}", headers=headers_owner)
        assert literature_diff.status_code == 200
        assert len(literature_diff.json()["publicationsRetained"]) == 2
        assert literature_diff.json()["contributionChanges"][0]["changes"]["evidence"]["added"] == [str(evidence_b2_id)]
        assert client.get(f"{base_b}/literature/compare?leftSnapshotId={snapshot_a_id}&rightSnapshotId={snapshot_b_id}", headers=headers_owner).status_code == 404
        assert client.get(f"{base_b}/literature/compare?leftSnapshotId={snapshot_b_id}&rightSnapshotId={snapshot_b2_id}", headers=headers_other).status_code == 404

        for suffix, forbidden in (
            ("knowledge/claims", str(claim_a_id)),
            ("knowledge/relationships", str(relation_a_id)),
            ("evidence", str(evidence_a_id)),
            ("hypotheses", str(hypothesis_a_id)),
            ("runs", str(run_a_id)),
            ("snapshots", str(snapshot_a_id)),
        ):
            response = client.get(f"{base_b}/{suffix}", headers=headers_owner)
            assert response.status_code == 200 and forbidden not in response.text
        assert client.get(f"{base_b}/knowledge/diff?leftSnapshotId={snapshot_a_id}&rightSnapshotId={snapshot_b_id}", headers=headers_owner).status_code == 404
        graph_diff = client.get(f"{base_b}/knowledge/diff?leftSnapshotId={snapshot_b_id}&rightSnapshotId={snapshot_b2_id}", headers=headers_owner)
        assert graph_diff.status_code == 200
        diff_data = graph_diff.json()
        assert [item["normalized_name"] for item in diff_data["entities"]["added"]] == ["added fixture entity"]
        assert [item["normalized_name"] for item in diff_data["entities"]["removed"]] == ["removed fixture entity"]
        relationship_change = diff_data["relationships"]["changed"]
        assert len(relationship_change) == 1
        assert relationship_change[0]["before"]["stance"] == "SUPPORTS"
        assert relationship_change[0]["after"]["stance"] == "CONTRADICTS"
        assert relationship_change[0]["before"]["confidence"] != relationship_change[0]["after"]["confidence"]
        assert len(relationship_change[0]["after"]["claim_ids"]) == 2
        snapshot_list = client.get(f"{base_b}/snapshots", headers=headers_owner)
        assert snapshot_list.status_code == 200
        snapshot_view = next(item for item in snapshot_list.json() if item["id"] == str(snapshot_b_id))
        shared_view = next(row for row in snapshot_view["manifest"]["entities"] if row["id"] == str(shared_id))
        assert snapshot_view["manifestRedacted"] is True and snapshot_view["digestValid"] is True
        assert snapshot_view["manifestResponseDigest"] == digest_json(snapshot_view["manifest"])
        assert shared_view["aliases"] == []
        assert set(shared_view["metadata"]["source_papers"]) == {str(paper_a_id), str(paper_b_id)}
        assert str(evidence_a_id) not in snapshot_list.text and str(claim_a_id) not in snapshot_list.text and "A-only alias" not in snapshot_list.text
        compare = client.get(f"{base_b}/snapshots/compare?leftSnapshotId={snapshot_b_id}&rightSnapshotId={snapshot_b2_id}", headers=headers_owner)
        assert compare.status_code == 200
        assert str(evidence_a_id) not in compare.text and str(claim_a_id) not in compare.text and "A-only alias" not in compare.text
        assert client.get(f"/api/v1/investigations/{investigation_a_id}/knowledge/entities/{shared_id}", headers=headers_other).status_code == 404

        with SessionLocal() as session:
            snapshot_a_after = session.get(ResearchSnapshot, snapshot_a_id)
            snapshot_b_after = session.get(ResearchSnapshot, snapshot_b_id)
            assert snapshot_a_after.manifest_digest == snapshot_a_digest
            assert snapshot_b_after.manifest_digest == snapshot_b_digest
            snapshot_b2_after = session.get(ResearchSnapshot, snapshot_b2_id)
            assert snapshot_b2_after.manifest_digest == snapshot_b2_digest
            entities_b = snapshot_b_after.manifest["entities"]
            shared_snapshot_entity = next(row for row in entities_b if row["id"] == str(shared_id))
            assert shared_snapshot_entity["aliases"] == ["A-only alias"]
            assert shared_snapshot_entity["metadata"]["source_papers"] == [str(paper_a_id), str(paper_b_id)]
        assert str(relation_a_id) in metta_a and str(relation_a_id) not in metta_b
        assert str(paper_a_id) in metta_a and str(paper_a_id) in metta_b
        assert str(evidence_a_id) not in metta_b and str(claim_a_id) not in metta_b
        assert "A-only fixture disease" not in metta_b
        assert metta_b == metta_b_repeat
    finally:
        with SessionLocal() as session:
            for investigation_id in (investigation_a_id, investigation_b_id, investigation_other_id):
                investigation = session.get(Investigation, investigation_id)
                if investigation:
                    session.delete(investigation)
            session.flush()
            for paper_id in (paper_a_id, paper_b_id):
                paper = session.get(Paper, paper_id)
                if paper:
                    session.delete(paper)
            for entity_id in (shared_id, private_a_id, target_b_id, removed_b_entity_id, added_b_entity_id):
                entity = session.get(Entity, entity_id)
                if entity:
                    session.delete(entity)
            for user_id in (owner_id, other_owner_id):
                user = session.get(User, user_id)
                if user:
                    session.delete(user)
            session.commit()
