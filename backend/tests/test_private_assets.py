from datetime import datetime, timezone
import hashlib
import uuid

import jwt
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import SessionLocal
from app.jobs import _write_artifact
from app.main import app
from app.models import AssetEvent, AssetRightsDeclaration, AssetVersion, Investigation, ResearchArtifact, ScientificAsset, User
from app.research_artifacts import generate_artifact
from app.research_reproducibility import create_run, freeze_snapshot
from test_phase4a_reproducibility import TEST_SECRET, _cleanup, _completed_investigation, _owner_id


def _cleanup_assets(investigation_id, paper_id):
    with SessionLocal() as session:
        assets = session.query(ScientificAsset).filter_by(investigation_id=investigation_id).all()
        for asset in assets:
            versions = session.query(AssetVersion).filter_by(asset_id=asset.id).all()
            version_ids = [v.id for v in versions]
            session.query(AssetEvent).filter_by(asset_id=asset.id).delete(synchronize_session=False)
            if version_ids:
                session.query(AssetRightsDeclaration).filter(AssetRightsDeclaration.asset_version_id.in_(version_ids)).delete(synchronize_session=False)
                session.query(AssetVersion).filter(AssetVersion.id.in_(version_ids)).delete(synchronize_session=False)
            session.delete(asset)
        session.commit()
    _cleanup(investigation_id, paper_id)


def _setup_asset(tmp_path, monkeypatch):
    investigation_id, paper_id = _completed_investigation()
    monkeypatch.setattr(get_settings(), "artifact_root", str(tmp_path))
    with SessionLocal() as session:
        investigation = session.get(Investigation, investigation_id)
        run = create_run(session, investigation, status="COMPLETED")
        run.completed_at = datetime.now(timezone.utc)
        snapshot = freeze_snapshot(session, investigation, run)
        generated = generate_artifact(snapshot, "MARKDOWN")
        content = generated.content if isinstance(generated.content, bytes) else generated.content.encode("utf-8")
        artifact = ResearchArtifact(snapshot_id=snapshot.id, artifact_type=generated.artifact_type,
            artifact_format=generated.artifact_format, status="COMPLETED", generator_version="test-1",
            schema_version="phase4a-1", content_digest=hashlib.sha256(content).hexdigest(),
            manifest_digest=snapshot.manifest_digest, storage_key=f"{snapshot.id}/test.md", visibility="PRIVATE",
            completed_at=datetime.now(timezone.utc))
        session.add(artifact); session.flush()
        _write_artifact(tmp_path, artifact.storage_key, content)
        session.commit()
        snapshot_id, artifact_id = snapshot.id, artifact.id
    headers = {"Authorization": f"Bearer {jwt.encode({'sub': str(_owner_id())}, TEST_SECRET, algorithm='HS256')}"}
    return investigation_id, paper_id, snapshot_id, artifact_id, headers


def test_private_asset_workflow_records_rights_and_verifies_integrity(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", TEST_SECRET); get_settings.cache_clear()
    inv, paper, snapshot, artifact, headers = _setup_asset(tmp_path, monkeypatch)
    client = TestClient(app)
    try:
        created = client.post(f"/api/v1/investigations/{inv}/assets", headers=headers, json={
            "asset_type": "RESEARCH_PACKAGE", "title": "Private package", "snapshot_id": str(snapshot), "artifact_id": str(artifact),
            "scientific_status": {"state": "PROVISIONAL", "uncertainty_level": "HIGH", "contradictory_evidence_count": 1}})
        assert created.status_code == 201, created.text
        asset = created.json()["asset"]; version = created.json()["version"]
        assert asset["created_by_user_id"] == str(_owner_id())
        assert "declared_owner" not in asset
        assert version["eligibility"]["eligible"] is False
        listed = client.get(f"/api/v1/investigations/{inv}/assets", headers=headers)
        assert listed.status_code == 200
        listed_asset = next(item for item in listed.json() if item["id"] == asset["id"])
        assert listed_asset["versions"][0]["id"] == version["id"]
        assert listed_asset["versions"][0]["snapshot_id"] == str(snapshot)
        assert listed_asset["versions"][0]["artifact_id"] == str(artifact)
        declared = client.post(f"/api/v1/investigations/{inv}/assets/{asset['id']}/rights-declarations", headers=headers, json={
            "declared_owner": {"type": "person", "display_name": "Declared Researcher"}, "ownership_basis": "Human assertion",
            "rights_scope": "This artifact version", "third_party_material": [{"status": "reviewed"}], "intended_use": "INTERNAL_RESEARCH"})
        assert declared.status_code == 201, declared.text
        assert declared.json()["declaration_actor_id"] == str(_owner_id())
        detail = client.get(f"/api/v1/investigations/{inv}/assets/{asset['id']}/provenance", headers=headers)
        assert detail.status_code == 200
        body = detail.json()
        assert body["verification"]["integrity_verified"] is True
        assert body["verification"]["scientific_validity"] == "NOT_ASSESSED"
        assert body["verification"]["legal_ownership"] == "NOT_ASSESSED"
        assert body["manifest"]["rights_status"] == "DECLARED"
        assert "Declared Researcher" not in str(body["manifest"])
        assert body["manifest"]["contradiction_count"] == 0
        assert body["manifest"]["scientific_status"]["uncertainty_level"] == "HIGH"
        unsafe = client.post(f"/api/v1/investigations/{inv}/assets", headers=headers, json={
            "asset_type": "RESEARCH_PACKAGE", "title": "Private package", "snapshot_id": str(snapshot), "artifact_id": str(artifact),
            "scientific_status": {"private_researcher_name": "Should not be accepted"}})
        assert unsafe.status_code == 422
        with SessionLocal() as session:
            rows = session.query(AssetVersion).filter(AssetVersion.id == version["id"]).all()
            assert len(rows) == 1 and rows[0].snapshot_id == snapshot and rows[0].artifact_id == artifact
    finally:
        _cleanup_assets(inv, paper)


def test_asset_rejects_mismatched_artifact_and_cross_owner_access(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", TEST_SECRET); get_settings.cache_clear()
    inv, paper, snapshot, artifact, headers = _setup_asset(tmp_path, monkeypatch)
    client = TestClient(app)
    try:
        wrong = client.post(f"/api/v1/investigations/{inv}/assets", headers=headers, json={
            "asset_type": "PACKAGE", "title": "Bad", "snapshot_id": str(snapshot), "artifact_id": str(uuid.uuid4())})
        assert wrong.status_code == 422
        with SessionLocal() as session:
            other = User(email=f"asset-test-{uuid.uuid4()}@example.invalid", role="USER")
            session.add(other); session.commit(); other_id = other.id
        other_headers = {"Authorization": f"Bearer {jwt.encode({'sub': str(other_id)}, TEST_SECRET, algorithm='HS256')}"}
        response = client.get(f"/api/v1/investigations/{inv}/assets", headers=other_headers)
        assert response.status_code == 404
    finally:
        _cleanup_assets(inv, paper)


def test_versions_are_additive_historical_versions_remain_readable(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", TEST_SECRET); get_settings.cache_clear()
    inv, paper, snapshot, artifact, headers = _setup_asset(tmp_path, monkeypatch)
    client = TestClient(app)
    try:
        created = client.post(f"/api/v1/investigations/{inv}/assets", headers=headers, json={
            "asset_type": "PACKAGE", "title": "Versioned", "snapshot_id": str(snapshot), "artifact_id": str(artifact)})
        assert created.status_code == 201
        asset_id = created.json()["asset"]["id"]
        first_id = created.json()["version"]["id"]
        second = client.post(f"/api/v1/investigations/{inv}/assets/{asset_id}/versions", headers=headers, json={
            "snapshot_id": str(snapshot), "artifact_id": str(artifact)})
        assert second.status_code == 201, second.text
        assert second.json()["version_number"] == 2
        assert second.json()["parent_version_id"] == first_id
        historical = client.get(f"/api/v1/investigations/{inv}/assets/{asset_id}/versions/{first_id}", headers=headers)
        assert historical.status_code == 200
        events = client.get(f"/api/v1/investigations/{inv}/assets/{asset_id}", headers=headers).json()["events"]
        assert [e["event_type"] for e in events].count("VERSION_CREATED") == 2
        assert client.put(f"/api/v1/investigations/{inv}/assets/{asset_id}/versions/{first_id}", headers=headers, json={}).status_code == 405
    finally:
        _cleanup_assets(inv, paper)


def test_create_rejects_artifact_bytes_digest_mismatch(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIXMIND_AUTH_SECRET", TEST_SECRET); get_settings.cache_clear()
    inv, paper, snapshot, artifact, headers = _setup_asset(tmp_path, monkeypatch)
    client = TestClient(app)
    try:
        with SessionLocal() as session:
            row = session.get(ResearchArtifact, artifact)
            path = tmp_path / row.storage_key
            path.write_bytes(path.read_bytes() + b"tampered")
        response = client.post(f"/api/v1/investigations/{inv}/assets", headers=headers, json={
            "asset_type": "PACKAGE", "title": "Tampered", "snapshot_id": str(snapshot), "artifact_id": str(artifact)})
        assert response.status_code == 422
        assert "digest" in response.text.lower()
    finally:
        _cleanup_assets(inv, paper)
