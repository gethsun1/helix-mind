'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ProtectedPage } from '../../../components/ProtectedPage';

type Snapshot = { id: string; snapshotNumber: number; runId: string; manifestDigest: string; digestValid: boolean };
type Artifact = { id: string; snapshotId: string; artifactType: string; artifactFormat: string; status: string; contentDigest: string | null; manifestDigest: string; fileSize: number | null };
type Check = { code: string; passed: boolean; message: string };
type Version = { id: string; version_number: number; snapshot_id: string; artifact_id: string; snapshot_manifest_digest: string; artifact_content_digest: string; status: string; eligibility: { eligible: boolean; checks: Check[] } };
type Asset = { id: string; title: string; asset_type: string; visibility: string; status: string; versions: Version[] };
type AssetDetail = { asset: Asset & { created_at: string }; versions: Version[]; rights_declarations: Array<{ id: string; asset_version_id: string; declared_owner: Record<string, unknown>; rights_status: string; conflict_status: string; ownership_basis: string; rights_scope: string; intended_use: string; declared_at: string }>; events: Array<{ id: string; event_type: string; reason: string | null; timestamp: string; new_status: string | null }> };
type Provenance = { manifest: Record<string, unknown>; manifest_digest: string; verification: { integrity_verified: boolean; checks: Check[]; scientific_validity: string; legal_ownership: string } };
type Anchor = { id: string; anchor_provider: string; anchor_type: string; external_reference: string; anchor_status: string; canonical_provenance_digest: string };
type AnchorCheck = { anchor_status: string; provider: string; snapshot_integrity: string; canonical_digest: string; artifact_bytes: string; external_anchor: string; independent_external_verification: boolean; scientific_validity: string; legal_ownership: string; licensing_authority: string };

const base = (id: string) => `/api/backend/api/v1/investigations/${id}/assets`;

export default function ScientificAssetsPage() {
  const { id } = useParams<{ id: string }>();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [detail, setDetail] = useState<AssetDetail | null>(null);
  const [provenance, setProvenance] = useState<Provenance | null>(null);
  const [anchors, setAnchors] = useState<Anchor[]>([]);
  const [anchorCheck, setAnchorCheck] = useState<AnchorCheck | null>(null);
  const [snapshotId, setSnapshotId] = useState('');
  const [artifactId, setArtifactId] = useState('');
  const [title, setTitle] = useState('');
  const [ownerName, setOwnerName] = useState('');
  const [ownershipBasis, setOwnershipBasis] = useState('');
  const [rightsScope, setRightsScope] = useState('');
  const [intendedUse, setIntendedUse] = useState('');
  const [conflictStatus, setConflictStatus] = useState('');
  const [contributors, setContributors] = useState('');
  const [licenseDeclaration, setLicenseDeclaration] = useState('');
  const [thirdPartyMaterial, setThirdPartyMaterial] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [assetsResponse, snapshotsResponse] = await Promise.all([
        fetch(base(id), { cache: 'no-store' }),
        fetch(`/api/backend/api/v1/investigations/${id}/snapshots`, { cache: 'no-store' }),
      ]);
      if (!assetsResponse.ok || !snapshotsResponse.ok) throw new Error('Scientific asset records could not be loaded.');
      const rows: Asset[] = await assetsResponse.json();
      const snapshotRows: Snapshot[] = await snapshotsResponse.json();
      setAssets(rows);
      setSnapshots(snapshotRows);
      setSelectedId(current => current && rows.some(row => row.id === current) ? current : rows[0]?.id ?? '');
      setSnapshotId(current => current && snapshotRows.some(row => row.id === current) ? current : snapshotRows[0]?.id ?? '');
      setError('');
    } catch (value) { setError(value instanceof Error ? value.message : 'Scientific asset records could not be loaded.'); }
    finally { setLoading(false); }
  }, [id]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!snapshotId) { setArtifacts([]); setArtifactId(''); return; }
    fetch(`/api/backend/api/v1/investigations/${id}/snapshots/${snapshotId}/artifacts`, { cache: 'no-store' })
      .then(async response => { if (!response.ok) throw new Error(); return response.json(); })
      .then((rows: Artifact[]) => { const completed = rows.filter(row => row.status === 'COMPLETED' && row.contentDigest); setArtifacts(completed); setArtifactId(current => completed.some(row => row.id === current) ? current : completed[0]?.id ?? ''); })
      .catch(() => { setArtifacts([]); setArtifactId(''); });
  }, [id, snapshotId]);

  const loadDetail = useCallback(async () => {
    if (!selectedId) { setDetail(null); setProvenance(null); setAnchors([]); return; }
    try {
      const [detailResponse, provenanceResponse] = await Promise.all([
        fetch(`${base(id)}/${selectedId}`, { cache: 'no-store' }),
        fetch(`${base(id)}/${selectedId}/provenance`, { cache: 'no-store' }),
      ]);
      if (!detailResponse.ok || !provenanceResponse.ok) throw new Error('Asset provenance details could not be loaded.');
      const value: AssetDetail = await detailResponse.json();
      const provenanceValue: Provenance = await provenanceResponse.json();
      setDetail(value); setProvenance(provenanceValue); setAnchorCheck(null); setError('');
      const version = value.versions[0];
      if (version) {
        const anchorResponse = await fetch(`${base(id)}/${selectedId}/versions/${version.id}/anchors`, { cache: 'no-store' });
        if (!anchorResponse.ok) throw new Error('Anchor status could not be loaded.');
        setAnchors(await anchorResponse.json());
      } else setAnchors([]);
    } catch (value) { setError(value instanceof Error ? value.message : 'Asset provenance details could not be loaded.'); }
  }, [id, selectedId]);

  useEffect(() => { void loadDetail(); }, [loadDetail]);
  const completedArtifacts = useMemo(() => artifacts.filter(item => item.snapshotId === snapshotId), [artifacts, snapshotId]);
  const rights = detail?.rights_declarations.find(item => item.asset_version_id === detail.versions[0]?.id);

  async function createAsset(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      const response = await fetch(base(id), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ asset_type: 'RESEARCH_ARTIFACT', title: title.trim(), snapshot_id: snapshotId, artifact_id: artifactId, status: 'DRAFT' }) });
      const value = await response.json();
      if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : 'Private asset could not be created.');
      setMessage('Private asset version created from the selected completed snapshot and artifact.'); setTitle(''); await load(); setSelectedId(value.asset.id);
    } catch (value) { setError(value instanceof Error ? value.message : 'Private asset could not be created.'); }
    finally { setBusy(false); }
  }

  async function declareRights(event: React.FormEvent) {
    event.preventDefault(); if (!detail) return; setBusy(true); setError(''); setMessage('');
    let thirdParty: unknown, contributorRows: unknown, license: unknown;
    try {
      thirdParty = JSON.parse(thirdPartyMaterial); contributorRows = JSON.parse(contributors); license = JSON.parse(licenseDeclaration);
      if (!Array.isArray(thirdParty) || !Array.isArray(contributorRows) || typeof license !== 'object' || license === null || Array.isArray(license)) throw new Error();
    } catch { setError('Contributors and third-party material must be JSON lists; license declaration must be a JSON object.'); setBusy(false); return; }
    try {
      const response = await fetch(`${base(id)}/${detail.asset.id}/rights-declarations`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ declared_owner: { name: ownerName.trim() }, contributors: contributorRows, ownership_basis: ownershipBasis.trim(), rights_scope: rightsScope.trim(), license_declaration: license, third_party_material: thirdParty, intended_use: intendedUse.trim(), conflict_status: conflictStatus }) });
      const value = await response.json();
      if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : 'Rights declaration could not be saved.');
      setMessage('Rights declaration recorded as a user statement; legal ownership is not assessed.'); await loadDetail(); await load();
    } catch (value) { setError(value instanceof Error ? value.message : 'Rights declaration could not be saved.'); }
    finally { setBusy(false); }
  }

  async function createAnchor() {
    const version = detail?.versions[0]; if (!detail || !version) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await fetch(`${base(id)}/${detail.asset.id}/versions/${version.id}/anchors`, { method: 'POST' });
      const value = await response.json();
      if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : 'Local test anchor could not be created.');
      setMessage('Deterministic local/test reference created. This is not public or external proof.'); await loadDetail();
    } catch (value) { setError(value instanceof Error ? value.message : 'Local test anchor could not be created.'); }
    finally { setBusy(false); }
  }

  async function verifyAnchor(anchor: Anchor) {
    const version = detail?.versions[0]; if (!detail || !version) return;
    setBusy(true); setError('');
    try {
      const response = await fetch(`${base(id)}/${detail.asset.id}/versions/${version.id}/anchors/${anchor.id}/verify`, { method: 'POST' });
      const value = await response.json(); if (!response.ok) throw new Error('Provenance verification failed to run.');
      setAnchorCheck(value); await loadDetail();
    } catch (value) { setError(value instanceof Error ? value.message : 'Provenance verification failed to run.'); }
    finally { setBusy(false); }
  }

  return <ProtectedPage eyebrow="INVESTIGATION / SCIENTIFIC IP" title="Scientific asset provenance.">
    <div className="asset-page">
      <Link className="button button-ghost button-small" href={`/investigations/${id}`}>← Investigation</Link>
      <p className="muted-copy">Private records bind an existing research snapshot and completed artifact. Rights are researcher declarations; scientific validity and legal ownership are assessed separately and remain unestablished here.</p>
      {error && <div className="panel" role="alert"><p className="error-text">{error}</p></div>}{message && <p className="asset-message" role="status">{message}</p>}
      {loading ? <div className="panel"><p>Loading private asset records…</p></div> : <div className="asset-layout">
        <section className="panel"><p className="eyebrow">INVESTIGATION-SCOPED ASSETS</p><h2>Private scientific assets</h2>{assets.length ? <div className="asset-list">{assets.map(asset => <button className={`asset-choice${selectedId === asset.id ? ' selected' : ''}`} key={asset.id} onClick={() => setSelectedId(asset.id)}><b>{asset.title}</b><small>{asset.asset_type} · {asset.status} · {asset.versions.length} version(s)</small></button>)}</div> : <p className="muted-copy">No asset records exist for this Investigation.</p>}
          <form className="asset-form" onSubmit={createAsset}><h3>Bind a completed artifact</h3><label className="filter-label">Asset title<input value={title} onChange={event => setTitle(event.target.value)} required maxLength={255} /></label><label className="filter-label">Completed snapshot<select value={snapshotId} onChange={event => setSnapshotId(event.target.value)} required><option value="">Choose snapshot</option>{snapshots.map(snapshot => <option key={snapshot.id} value={snapshot.id}>Snapshot {snapshot.snapshotNumber} · {snapshot.digestValid ? 'digest verified' : 'digest mismatch'}</option>)}</select></label><label className="filter-label">Completed artifact<select value={artifactId} onChange={event => setArtifactId(event.target.value)} required><option value="">Choose artifact</option>{completedArtifacts.map(artifact => <option key={artifact.id} value={artifact.id}>{artifact.artifactType} · {artifact.contentDigest?.slice(0, 12)}</option>)}</select></label><button className="button button-small" disabled={busy || !snapshotId || !artifactId || !title.trim()}>{busy ? 'Saving…' : 'Create private asset version'}</button></form>
        </section>
        {detail && provenance ? <section className="panel asset-detail"><div className="panel-heading"><div><p className="eyebrow">ASSET IDENTITY</p><h2>{detail.asset.title}</h2></div><span className="status-chip">{detail.asset.status}</span></div><p className="paper-meta">{detail.asset.asset_type} · PRIVATE · asset {detail.asset.id}</p>
          <h3>Version and immutable bindings</h3>{detail.versions.map(version => <article className="asset-version" key={version.id}><b>Version {version.version_number} · {version.status}</b><small>Version {version.id} · snapshot {version.snapshot_id} · artifact {version.artifact_id}</small><small>Snapshot manifest SHA-256 <code>{version.snapshot_manifest_digest}</code></small><small>Artifact content SHA-256 <code>{version.artifact_content_digest}</code></small></article>)}
          <h3>Integrity verification</h3><p className="asset-verdict">{provenance.verification.integrity_verified ? 'Integrity references verified' : 'Integrity checks incomplete or failed'} · manifest {provenance.manifest_digest}</p><div className="asset-checks">{provenance.verification.checks.map(check => <div key={check.code}><span className={check.passed ? 'check-pass' : 'check-pending'}>{check.passed ? 'PASS' : 'NOT MET'}</span><span>{check.message}</span></div>)}</div>
          <h3>Rights declaration</h3>{rights ? <div className="asset-version"><b>{rights.rights_status} · {rights.conflict_status}</b><small>Declared owner: {String(rights.declared_owner.name ?? 'not specified')}</small><small>{rights.ownership_basis}</small><small>Scope: {rights.rights_scope} · intended use: {rights.intended_use}</small><small>Recorded {new Date(rights.declared_at).toLocaleString()}</small><p className="phase-disclaimer">A declaration records a researcher statement. It does not establish legal ownership or licensing authority.</p></div> : <form className="asset-form" onSubmit={declareRights}><p className="muted-copy">Enter the declaration to record. HelixMind does not validate title or legal authority. Enter `[]` or `{}` only when that is your intended declaration.</p><label className="filter-label">Declared owner name<input value={ownerName} onChange={event => setOwnerName(event.target.value)} required /></label><label className="filter-label">Ownership basis<input value={ownershipBasis} onChange={event => setOwnershipBasis(event.target.value)} required maxLength={4000} /></label><label className="filter-label">Rights scope<input value={rightsScope} onChange={event => setRightsScope(event.target.value)} required maxLength={4000} /></label><label className="filter-label">Intended use<input value={intendedUse} onChange={event => setIntendedUse(event.target.value)} required maxLength={64} /></label><label className="filter-label">Conflict declaration<select value={conflictStatus} onChange={event => setConflictStatus(event.target.value)} required><option value="">Choose declaration</option><option value="NONE_DECLARED">No conflict declared</option><option value="UNRESOLVED">Conflict unresolved</option></select></label><label className="filter-label">Contributors (JSON list)<textarea value={contributors} onChange={event => setContributors(event.target.value)} required rows={2} /></label><label className="filter-label">License declaration (JSON object)<textarea value={licenseDeclaration} onChange={event => setLicenseDeclaration(event.target.value)} required rows={2} /></label><label className="filter-label">Third-party material declaration (JSON list)<textarea value={thirdPartyMaterial} onChange={event => setThirdPartyMaterial(event.target.value)} required rows={2} /></label><button className="button button-small" disabled={busy || !ownerName.trim() || !ownershipBasis.trim() || !rightsScope.trim() || !intendedUse.trim() || !conflictStatus || !contributors.trim() || !licenseDeclaration.trim() || !thirdPartyMaterial.trim()}>{busy ? 'Saving…' : 'Record rights declaration'}</button></form>}
          <h3>Provenance anchor</h3>{anchors.length ? <div className="asset-list">{anchors.map(anchor => <article className="asset-version" key={anchor.id}><b>{anchor.anchor_status} · {anchor.anchor_provider}</b><small>{anchor.anchor_type} · reference {anchor.external_reference}</small><small>Canonical provenance SHA-256 {anchor.canonical_provenance_digest}</small><p className="phase-disclaimer">Local/test reference only. No independent external verification or public anchoring is provided.</p><button className="button button-ghost button-small" disabled={busy} onClick={() => void verifyAnchor(anchor)}>Verify local reference</button></article>)}</div> : <><p className="muted-copy">{detail.versions[0]?.eligibility.eligible ? 'No local/test reference recorded.' : 'Anchor eligibility requires all listed checks, including a rights declaration.'}</p><button className="button button-ghost button-small" disabled={busy || !detail.versions[0]?.eligibility.eligible} onClick={() => void createAnchor()}>{busy ? 'Working…' : 'Create local/test reference'}</button></>}{anchorCheck && <div className="query-callout"><b>{anchorCheck.anchor_status} · {anchorCheck.provider}</b><small>Snapshot {anchorCheck.snapshot_integrity} · canonical digest {anchorCheck.canonical_digest} · artifact bytes {anchorCheck.artifact_bytes}</small><small>External verification: {anchorCheck.independent_external_verification ? 'yes' : 'no'} · scientific validity: {anchorCheck.scientific_validity} · legal ownership: {anchorCheck.legal_ownership} · licensing authority: {anchorCheck.licensing_authority}</small></div>}
          <h3>Audit events</h3>{detail.events.length ? <div className="asset-list">{detail.events.map(event => <article className="asset-version" key={event.id}><b>{event.event_type}{event.new_status ? ` · ${event.new_status}` : ''}</b><small>{event.reason || 'No event reason recorded'} · {new Date(event.timestamp).toLocaleString()}</small></article>)}</div> : <p className="muted-copy">No audit events are recorded.</p>}
          <div className="asset-boundaries"><b>Interpretation boundary</b><span>Integrity: {provenance.verification.integrity_verified ? 'verified against stored references' : 'not fully verified'}</span><span>Declared rights: {rights?.rights_status ?? 'not declared'}</span><span>Scientific validity: {provenance.verification.scientific_validity}</span><span>Legal ownership: {provenance.verification.legal_ownership}</span><span>External provenance: {anchors.some(anchor => anchor.anchor_provider !== 'test/local') ? 'provider recorded; independently verify scope' : 'not externally anchored'}</span><span>Production external provider: unresolved / not configured</span></div>
        </section> : <section className="panel empty-state"><h3>Select an existing asset</h3><p>Asset versions, rights declarations, provenance checks, and audit events will appear here.</p></section>}
      </div>}
    </div>
  </ProtectedPage>;
}
