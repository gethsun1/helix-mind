'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { ProtectedPage } from '../../../components/ProtectedPage';

type Publication = { publicationId: string; title: string; identifiers: { pmid: string | null; pmcid: string | null; doi: string | null }; source: string; counts: Record<string, number>; relevance: { score: number; formulaVersion: string; meaning: string }; contributions: { evidence: { id: string; text: string; polarity: string | null }[]; claims: { id: string; text: string }[]; relationships: { id: string; predicate: string; stance: string }[]; propositions: { id: string; text: string }[]; hypotheses: { id: string; statement: string; status: string }[] } };
type Intelligence = { publications: Publication[]; landscape: Record<string, number>; coverage: { note: string; propositionPublicationSupport: { propositionId: string; publicationCount: number; coverage: string }[] } };
type Snapshot = { id: string; snapshotNumber: number };
type Diff = { publicationsAdded: unknown[]; publicationsRemoved: unknown[]; publicationsRetained: unknown[]; contributionChanges: { publicationId: string; title: string; changes: Record<string, { added: string[]; removed: string[] }> }[] };

export default function InvestigationLiteraturePage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<Intelligence | null>(null);
  const [error, setError] = useState('');
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [leftSnapshot, setLeftSnapshot] = useState('');
  const [rightSnapshot, setRightSnapshot] = useState('');
  const [diff, setDiff] = useState<Diff | null>(null);
  const [diffError, setDiffError] = useState('');
  useEffect(() => { fetch(`/api/backend/api/v1/investigations/${id}/literature/intelligence`, { cache: 'no-store' }).then(async response => { if (!response.ok) throw new Error(response.status === 404 ? 'Investigation not found.' : 'Literature intelligence could not be loaded.'); setData(await response.json()); }).catch(value => setError(value.message)); fetch(`/api/backend/api/v1/investigations/${id}/snapshots`, { cache: 'no-store' }).then(response => response.ok ? response.json() : []).then((rows: Snapshot[]) => { setSnapshots(rows); setLeftSnapshot(rows[1]?.id ?? ''); setRightSnapshot(rows[0]?.id ?? ''); }).catch(() => setSnapshots([])); }, [id]);
  async function compare() { setDiffError(''); setDiff(null); const query = new URLSearchParams({ leftSnapshotId: leftSnapshot, rightSnapshotId: rightSnapshot }); const response = await fetch(`/api/backend/api/v1/investigations/${id}/literature/compare?${query}`, { cache: 'no-store' }); if (!response.ok) { setDiffError('Literature snapshots could not be compared.'); return; } setDiff(await response.json()); }
  return <ProtectedPage eyebrow="INVESTIGATION / LITERATURE INTELLIGENCE" title="Literature landscape."><div className="literature-page">
    <Link className="button button-ghost button-small" href={`/investigations/${id}`}>← Investigation</Link>
    {error ? <div className="panel"><p className="error-text">{error}</p></div> : !data ? <div className="panel"><p>Loading investigation literature…</p></div> : <>
      <div className="health-grid">{[['Publications', data.landscape.totalPublications], ['Evidence bearing', data.landscape.evidenceBearingPublications], ['Graph linked', data.landscape.graphContributingPublications], ['Proposition linked', data.landscape.propositionContributingPublications], ['Hypothesis linked', data.landscape.hypothesisContributingPublications]].map(([name, value]) => <div className="health-card" key={String(name)}><span>{name}</span><b>{value}</b></div>)}</div>
      {snapshots.length > 1 && <section className="panel"><p className="eyebrow">RUN-TO-RUN LITERATURE</p><h2>Compare immutable snapshots</h2><div className="filter-row"><label>Earlier snapshot<select value={leftSnapshot} onChange={event => setLeftSnapshot(event.target.value)}>{snapshots.map(row => <option value={row.id} key={row.id}>Snapshot {row.snapshotNumber}</option>)}</select></label><label>Later snapshot<select value={rightSnapshot} onChange={event => setRightSnapshot(event.target.value)}>{snapshots.map(row => <option value={row.id} key={row.id}>Snapshot {row.snapshotNumber}</option>)}</select></label><button className="button button-small" disabled={!leftSnapshot || !rightSnapshot || leftSnapshot === rightSnapshot} onClick={() => void compare()}>Compare</button></div>{diffError && <p className="error-text">{diffError}</p>}{diff && <><p>{diff.publicationsAdded.length} new · {diff.publicationsRemoved.length} no longer retrieved · {diff.publicationsRetained.length} retained publications</p>{diff.contributionChanges.map(change => <p className="paper-meta" key={change.publicationId}>{change.title}: {Object.entries(change.changes).map(([kind, values]) => `${kind} +${values.added.length}/−${values.removed.length}`).join(' · ')}</p>)}<small>Comparison reads immutable snapshot manifests; historical runs are unchanged.</small></>}</section>}
      <p className="phase-disclaimer">Relevance is deterministic investigation linkage (formula {data.publications[0]?.relevance.formulaVersion ?? 'literature-relevance-v1'}), not evidence confidence or scientific truth. {data.coverage.note}</p>
      {data.publications.map(paper => <article className="paper-card" key={paper.publicationId}>
        <div className="paper-card-top"><span className="source-label">{paper.source}</span><span className="relevance-label">Relevance {Math.round(paper.relevance.score * 100)}%</span></div>
        <h3><Link href={`/investigations/${id}/literature/${paper.publicationId}`}>{paper.title}</Link></h3>
        <p className="paper-meta">{paper.counts.evidence} evidence · {paper.counts.claims} claims · {paper.counts.entities} entities · {paper.counts.relationships} relationships · {paper.counts.propositions} propositions · {paper.counts.hypotheses} hypotheses</p>
        <div className="paper-card-bottom">{paper.identifiers.pmid && <span>PMID {paper.identifiers.pmid}</span>}{paper.identifiers.doi && <span>DOI {paper.identifiers.doi}</span>}{paper.identifiers.pmcid && <span>PMCID {paper.identifiers.pmcid}</span>}</div>
        {paper.contributions.evidence.map(item => <div className="evidence-card" key={item.id}><p>{item.text}</p><small>{item.polarity || 'Polarity unavailable'} · source evidence</small></div>)}
        {paper.contributions.relationships.map(item => <p className="paper-meta" key={item.id}>Graph relationship: {item.predicate} · {item.stance}</p>)}
        {paper.contributions.propositions.map(item => <p className="paper-meta" key={item.id}>Proposition: {item.text}</p>)}
        {paper.contributions.hypotheses.map(item => <p className="paper-meta" key={item.id}>Hypothesis: {item.statement} · {item.status}</p>)}
      </article>)}
      {data.publications.length === 0 && <div className="panel empty-state"><h3>No retrieved publications</h3><p>Run literature retrieval for this investigation to build an evidence linked landscape.</p></div>}
      <div className="panel"><p className="eyebrow">LIMITED SUPPORT</p><h2>Proposition coverage</h2>{data.coverage.propositionPublicationSupport.length ? data.coverage.propositionPublicationSupport.map(item => <p className="paper-meta" key={item.propositionId}>{item.coverage} · {item.publicationCount} publications · proposition {item.propositionId.slice(0, 8)}</p>) : <p className="muted-copy">No persisted proposition publication links are available yet.</p>}</div>
    </>}
  </div></ProtectedPage>;
}
