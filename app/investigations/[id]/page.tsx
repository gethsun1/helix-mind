'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { ProtectedShell } from '../../components/ProtectedShell';

type Event = { id: string; type: string; message: string; metadata: Record<string, unknown> | null; createdAt: string };
type Paper = { id: string; source: string; sourceRecords: string[]; title: string; abstract: string | null; authors: string[] | null; journal: string | null; publicationDate: string | null; doi: string | null; pmid: string | null; pmcid: string | null; url: string | null; relevanceScore: number | null; relevanceReason: string | null; sourceQuery: string | null; rank: number | null };
type PaperPage = { items: Paper[]; total: number; page: number; pageSize: number; pageCount: number };
type Search = { id: string; source: string; query: string; filters: Record<string, unknown> | null; executedAt: string; resultCount: number; status: string; errorMessage: string | null; reused: boolean };
type Milestone = { key: string; label: string; status: string; achievedAt: string | null; evidence: string };
type Health = { papers: number; searches: number; claims: number; evidence: number; evidenceWithProvenance: number; propositions: number; hypotheses: number; contradictions: number; knowledgeGaps: number };
type Investigation = { id: string; title: string; researchQuestion: string; domain: string; status: string; createdAt: string; updatedAt: string; startedAt: string | null; completedAt: string | null; errorMessage: string | null; researchPlan: Record<string, unknown> | null; events: Event[]; milestones: Milestone[]; health: Health | null };
type Evidence = { id: string; paperId: string | null; propositionId: string | null; extractedText: string; sourceLocation: string; sourceSpan?: Record<string, unknown> | null; polarity: string | null; strength: number; confidence: number; provenance: Record<string, unknown> | null };
type Proposition = { id: string; subject: string; predicate: string; object: string; description: string };
type Hypothesis = { id: string; proposition: Proposition | null; statement: string; status: string; confidence: number; supportingEvidenceCount: number; contradictoryEvidenceCount: number; supportingEvidence: Evidence[]; contradictoryEvidence: Evidence[]; uncertainty: Record<string, unknown> | null };
type Contradiction = { id: string; proposition: Proposition; supportingEvidence: Evidence; contradictoryEvidence: Evidence; contradictionType: string; confidence: number };
type Gap = { id: string; description: string; severity: string; status: string; evidenceCount: number; contradictionCount: number; confidence: number; rationale: string | null; researchOpportunity: string | null };
type Trace = { id: string; hypothesisId: string; reasoningSummary: string; ruleName: string; confidence: number; trace: { starting_proposition?: { subject: string; predicate: string; object: string }; supporting_evidence?: string[]; contradictory_evidence?: string[]; result?: string; uncertainty?: Record<string, unknown> } };
type Reasoning = { hypotheses: number; contradictions: number; knowledgeGaps: number; traces: number; items: Trace[] };
type Run = { id: string; runNumber: number; status: string; snapshotId: string | null; parentRunId: string | null; startedAt: string | null; completedAt: string | null };
type Snapshot = { id: string; runId: string; snapshotNumber: number; manifestDigest: string; formulaVersion: string | null; createdAt: string };
type Artifact = { id: string; snapshotId: string; artifactType: string; artifactFormat: string; status: string; contentDigest: string | null; contentType: string | null; fileSize: number | null; errorMessage: string | null; downloadUrl: string | null; completedAt: string | null };

const PLAN_FIELDS = ['research_objectives', 'research_questions', 'search_strategies', 'key_concepts', 'evidence_categories', 'reasoning_tasks'];
const ARTIFACT_TYPES = [['MARKDOWN', 'Markdown research export'], ['SCIENTIFIC_REPORT', 'Structured scientific report'], ['OBSIDIAN_VAULT', 'Obsidian vault (.zip)']] as const;
function pretty(value: string) { return value.replaceAll('_', ' '); }
function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'; }
function formatPaperDate(value: string | null) { return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value)) : 'Publication date unavailable'; }
function formatBytes(value: number | null) { if (value === null) return 'Size unavailable'; if (value < 1024) return `${value} B`; if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`; return `${(value / (1024 * 1024)).toFixed(1)} MB`; }
function confidence(value: number) { return `${Math.round(value * 100)}%`; }

export default function InvestigationPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [papers, setPapers] = useState<PaperPage | null>(null);
  const [searches, setSearches] = useState<Search[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [contradictions, setContradictions] = useState<Contradiction[]>([]);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [reasoning, setReasoning] = useState<Reasoning | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState('');
  const [paperPage, setPaperPage] = useState(1);
  const [source, setSource] = useState('');
  const [evidencePolarity, setEvidencePolarity] = useState('');
  const [minimumConfidence, setMinimumConfidence] = useState('');
  const [error, setError] = useState('');
  const [artifactError, setArtifactError] = useState('');
  const [busy, setBusy] = useState(false);
  const [artifactBusy, setArtifactBusy] = useState(false);

  const load = useCallback(async () => {
    const paperQuery = new URLSearchParams({ page: String(paperPage), pageSize: '8' });
    if (source) paperQuery.set('source', source);
    const evidenceQuery = new URLSearchParams({ limit: '500', provenanceOnly: 'true' });
    if (source) evidenceQuery.set('paperSource', source);
    if (evidencePolarity) evidenceQuery.set('polarity', evidencePolarity);
    if (minimumConfidence) evidenceQuery.set('minConfidence', minimumConfidence);
    const [investigationResponse, papersResponse, searchesResponse, evidenceResponse, hypothesesResponse, contradictionsResponse, gapsResponse, reasoningResponse, runsResponse, snapshotsResponse] = await Promise.all([
      fetch(`/api/backend/api/v1/investigations/${id}`, { cache: 'no-store' }),
      fetch(`/api/backend/api/v1/investigations/${id}/papers?${paperQuery}`, { cache: 'no-store' }),
      fetch(`/api/backend/api/v1/investigations/${id}/searches`, { cache: 'no-store' }),
      fetch(`/api/backend/api/v1/investigations/${id}/evidence?${evidenceQuery}`, { cache: 'no-store' }),
      fetch(`/api/backend/api/v1/investigations/${id}/hypotheses`, { cache: 'no-store' }),
      fetch(`/api/backend/api/v1/investigations/${id}/contradictions`, { cache: 'no-store' }),
      fetch(`/api/backend/api/v1/investigations/${id}/knowledge-gaps`, { cache: 'no-store' }),
      fetch(`/api/backend/api/v1/investigations/${id}/reasoning`, { cache: 'no-store' }),
      fetch(`/api/backend/api/v1/investigations/${id}/runs`, { cache: 'no-store' }),
      fetch(`/api/backend/api/v1/investigations/${id}/snapshots`, { cache: 'no-store' }),
    ]);
    if (!investigationResponse.ok) { setError(investigationResponse.status === 404 ? 'Investigation not found.' : 'Investigation could not be loaded.'); return; }
    setInvestigation(await investigationResponse.json());
    if (papersResponse.ok) setPapers(await papersResponse.json());
    if (searchesResponse.ok) setSearches(await searchesResponse.json());
    if (evidenceResponse.ok) setEvidence(await evidenceResponse.json());
    if (hypothesesResponse.ok) setHypotheses(await hypothesesResponse.json());
    if (contradictionsResponse.ok) setContradictions(await contradictionsResponse.json());
    if (gapsResponse.ok) setGaps(await gapsResponse.json());
    if (reasoningResponse.ok) setReasoning(await reasoningResponse.json());
    if (runsResponse.ok) setRuns(await runsResponse.json());
    if (snapshotsResponse.ok) {
      const values: Snapshot[] = await snapshotsResponse.json();
      setSnapshots(values);
      setSelectedSnapshotId(current => current && values.some(item => item.id === current) ? current : values[0]?.id ?? '');
    }
    setError('');
  }, [id, paperPage, source, evidencePolarity, minimumConfidence]);

  const loadArtifacts = useCallback(async () => {
    if (!selectedSnapshotId) { setArtifacts([]); return; }
    const response = await fetch(`/api/backend/api/v1/investigations/${id}/snapshots/${selectedSnapshotId}/artifacts`, { cache: 'no-store' });
    if (response.ok) { setArtifacts(await response.json()); setArtifactError(''); } else setArtifactError('Artifact status could not be loaded.');
  }, [id, selectedSnapshotId]);

  useEffect(() => { void load(); const timer = window.setInterval(() => void load(), 5000); return () => window.clearInterval(timer); }, [load]);
  useEffect(() => { void loadArtifacts(); const timer = window.setInterval(() => void loadArtifacts(), 5000); return () => window.clearInterval(timer); }, [loadArtifacts]);

  async function cancel() {
    setBusy(true); setError('');
    const response = await fetch(`/api/backend/api/v1/investigations/${id}/cancel`, { method: 'POST' });
    if (!response.ok) setError('This investigation could not be cancelled.');
    await load(); setBusy(false);
  }

  async function rerun() {
    setBusy(true); setError('');
    const response = await fetch(`/api/backend/api/v1/investigations/${id}/runs`, { method: 'POST' });
    if (!response.ok) setError('A reproducible rerun could not be queued.');
    await load(); setBusy(false);
  }

  async function createSnapshot() {
    setArtifactBusy(true); setArtifactError('');
    const response = await fetch(`/api/backend/api/v1/investigations/${id}/snapshots`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    if (!response.ok) setArtifactError('A completed investigation snapshot could not be created.');
    else { const snapshot: Snapshot = await response.json(); setSelectedSnapshotId(snapshot.id); await load(); }
    setArtifactBusy(false);
  }

  async function generateArtifact(artifactType: string) {
    if (!selectedSnapshotId) return;
    setArtifactBusy(true); setArtifactError('');
    const response = await fetch(`/api/backend/api/v1/investigations/${id}/snapshots/${selectedSnapshotId}/artifacts`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ artifactType }) });
    if (!response.ok) setArtifactError('This artifact could not be queued.');
    else await loadArtifacts();
    setArtifactBusy(false);
  }

  const planEntries = useMemo(() => PLAN_FIELDS.filter(key => Array.isArray(investigation?.researchPlan?.[key])), [investigation]);
  const sourceCounts = useMemo(() => papers?.items.reduce<Record<string, number>>((counts, paper) => { for (const item of paper.sourceRecords.length ? paper.sourceRecords : [paper.source]) counts[item] = (counts[item] || 0) + 1; return counts; }, {}) ?? {}, [papers]);
  const dedupEvent = investigation?.events.find(event => event.type === 'papers_deduplicated');
  const duplicatesRemoved = typeof dedupEvent?.metadata?.duplicates_removed === 'number' ? dedupEvent.metadata.duplicates_removed : 0;
  const canRerun = ['COMPLETED', 'FAILED', 'CANCELLED'].includes(investigation?.status.toUpperCase() ?? '');
  const selectedSnapshot = snapshots.find(item => item.id === selectedSnapshotId);

  return <ProtectedShell><div className="page-wrap investigation-workspace">{error && !investigation ? <div className="panel"><p className="error-text">{error}</p></div> : !investigation ? <div className="panel"><p>Loading investigation…</p></div> : <>
    <p className="eyebrow">RESEARCH / INVESTIGATION</p>
    <div className="workspace-title"><div><span className={`status-chip status-${investigation.status.toLowerCase()}`}>{pretty(investigation.status)}</span><h1>{investigation.title}</h1><p className="workspace-question">{investigation.researchQuestion}</p><small className="mono">{investigation.domain} · created {formatDate(investigation.createdAt)}</small></div><div className="workspace-actions">{investigation.status.toUpperCase() === 'QUEUED' && <button className="button button-ghost" onClick={cancel} disabled={busy}>{busy ? 'Cancelling…' : 'Cancel investigation'}</button>}{canRerun && <button className="button" onClick={rerun} disabled={busy}>{busy ? 'Queueing…' : 'Re-run investigation ↗'}</button>}</div></div>
    {error && <p className="error-text">{error}</p>}
    <section className="progress-panel panel"><div className="panel-heading"><div><p className="eyebrow">RESEARCH QUEST</p><h2>Investigation progression</h2></div><span className="phase-note">DERIVED FROM RECORDS</span></div><div className="milestone-grid">{(investigation.milestones ?? []).map(item => <div className={`milestone milestone-${item.status.toLowerCase()}`} key={item.key}><span className="milestone-marker">{item.status === 'ACHIEVED' ? '✓' : item.status === 'CURRENT' ? '•' : '○'}</span><div><b>{item.label}</b><small>{item.status.toLowerCase()} · {item.evidence}</small>{item.achievedAt && <small>{formatDate(item.achievedAt)}</small>}</div></div>)}</div></section>
    <div className="health-grid">{[['Papers', investigation.health?.papers ?? 0], ['Evidence', investigation.health?.evidence ?? 0], ['With provenance', investigation.health?.evidenceWithProvenance ?? 0], ['Propositions', investigation.health?.propositions ?? 0], ['Hypotheses', investigation.health?.hypotheses ?? 0], ['Open gaps', investigation.health?.knowledgeGaps ?? 0]].map(([label, value]) => <div className="health-card" key={String(label)}><span>{label}</span><b>{value}</b></div>)}</div>
    <div className="workspace-grid"><section>
      <div className="panel literature-panel"><div className="panel-heading"><div><p className="eyebrow">LITERATURE</p><h2>Source-grounded papers</h2></div><span className="phase-note">Phase 3C</span></div><div className="literature-metrics"><div><b>{papers?.total ?? 0}</b><span>unique papers</span></div><div><b>{sourceCounts.PUBMED ?? 0}</b><span>PubMed records</span></div><div><b>{sourceCounts.EUROPE_PMC ?? 0}</b><span>Europe PMC records</span></div><div><b>{duplicatesRemoved}</b><span>duplicates removed</span></div></div>{papers && papers.items.length > 0 ? <><div className="paper-list">{papers.items.map(paper => <article className="paper-card" key={paper.id}><div className="paper-card-top"><span className="source-label">{paper.sourceRecords.join(' · ')}</span>{paper.relevanceScore !== null && <span className="relevance-label">Relevance {Math.round(paper.relevanceScore * 100)}%</span>}</div><h3><Link href={`/literature/${paper.id}`}>{paper.title}</Link></h3><p className="paper-meta">{paper.authors?.slice(0, 4).join(', ') || 'Author information unavailable'} · {paper.journal || 'Journal unavailable'} · {formatPaperDate(paper.publicationDate)}</p><p className="paper-abstract">{paper.abstract || 'Abstract unavailable from source.'}</p><div className="paper-card-bottom">{paper.pmid && <span>PMID {paper.pmid}</span>}{paper.doi && <span>DOI {paper.doi}</span>}{paper.url && <a href={paper.url} target="_blank" rel="noreferrer">Original source ↗</a>}</div></article>)}</div><div className="pagination"><button className="button button-ghost button-small" disabled={paperPage <= 1} onClick={() => setPaperPage(value => value - 1)}>← Previous</button><span>Page {papers.page} of {papers.pageCount}</span><button className="button button-ghost button-small" disabled={paperPage >= papers.pageCount} onClick={() => setPaperPage(value => value + 1)}>Next →</button></div></> : <div className="plan-empty"><span>∴</span><p>{investigation.status.toUpperCase() === 'SEARCHING' ? 'Literature sources are being queried.' : 'No papers were returned by the available sources.'}</p></div>}<p className="phase-disclaimer">Relevance is a transparent ordering signal based on plan-concept overlap and recency. It is not scientific evidence strength.</p></div>
      <div className="panel"><div className="panel-heading"><div><p className="eyebrow">OMEGACLAW PLAN</p><h2>Research strategy</h2></div></div>{investigation.researchPlan && planEntries.length > 0 ? <div className="plan-grid">{planEntries.map(key => <div className="plan-block" key={key}><h3>{pretty(key)}</h3><ul>{(investigation.researchPlan?.[key] as string[]).map((item, index) => <li key={`${key}-${index}`}>{item}</li>)}</ul></div>)}</div> : <div className="plan-empty"><span>∴</span><p>{investigation.status.toUpperCase() === 'FAILED' ? investigation.errorMessage : 'OmegaClaw is preparing the structured research plan.'}</p></div>}<p className="phase-disclaimer">The reasoning panels preserve source evidence, uncertainty, and the deterministic inference trace.</p></div>
    </section><aside>
      <div className="panel event-panel"><p className="eyebrow">AUDIT TRAIL</p><h2>Processing events</h2>{investigation.events.length === 0 ? <p className="muted-copy">No processing events recorded.</p> : <div className="timeline">{investigation.events.map(event => <div className="timeline-item" key={event.id}><span className="timeline-marker" /><div><b>{pretty(event.type)}</b><p>{event.message}</p><small>{formatDate(event.createdAt)}</small></div></div>)}</div>}</div>
      <div className="panel search-panel"><p className="eyebrow">RESEARCH SOURCES</p><h2>Searches executed</h2>{searches.length === 0 ? <p className="muted-copy">Source searches will appear here after the worker starts.</p> : <div className="search-list">{searches.map(search => <div className="search-record" key={search.id}><div><b>{search.source}</b><small>{search.status}{search.reused ? ' · reused' : ''} · {search.resultCount} records</small></div><code>{search.query}</code><small>{formatDate(search.executedAt)}</small></div>)}</div>}</div>
      <div className="panel artifact-panel"><div className="panel-heading"><div><p className="eyebrow">PHASE 4B / ARTIFACTS</p><h2>Research exports</h2></div><span className="phase-note">PRIVATE</span></div><p className="muted-copy">Exports are generated from an immutable snapshot and remain owner-scoped.</p>{snapshots.length === 0 ? <><p className="muted-copy">No snapshot is available yet. Completed investigations can be frozen before export.</p><button className="button button-small" onClick={createSnapshot} disabled={artifactBusy || !canRerun}>{artifactBusy ? 'Freezing…' : 'Create snapshot'}</button></> : <><label className="filter-label">Snapshot<select value={selectedSnapshotId} onChange={event => setSelectedSnapshotId(event.target.value)}>{snapshots.map(snapshot => <option value={snapshot.id} key={snapshot.id}>Snapshot {snapshot.snapshotNumber} · {snapshot.manifestDigest.slice(0, 10)}</option>)}</select></label>{selectedSnapshot && <small className="artifact-meta">Run {selectedSnapshot.runId.slice(0, 8)} · {selectedSnapshot.formulaVersion || 'formula unavailable'} · created {formatDate(selectedSnapshot.createdAt)}</small>}<div className="artifact-actions">{ARTIFACT_TYPES.map(([type, label]) => <button className="button button-ghost button-small" key={type} onClick={() => generateArtifact(type)} disabled={artifactBusy}>{label}</button>)}</div>{artifactError && <p className="error-text">{artifactError}</p>}<div className="artifact-list">{artifacts.length === 0 ? <p className="muted-copy">No exports generated for this snapshot.</p> : artifacts.map(artifact => <div className="artifact-record" key={artifact.id}><div><b>{pretty(artifact.artifactType)}</b><small>{artifact.status} · {formatBytes(artifact.fileSize)}</small></div>{artifact.status === 'COMPLETED' && artifact.downloadUrl ? <a className="button button-small" href={artifact.downloadUrl}>Download</a> : <small>{artifact.errorMessage || 'Queued for generation.'}</small>}</div>)}</div></>}</div>
      <div className="panel"><label className="filter-label">PAPER SOURCE<select value={source} onChange={event => { setSource(event.target.value); setPaperPage(1); }}><option value="">All sources</option><option value="PUBMED">PubMed</option><option value="EUROPE_PMC">Europe PMC</option></select></label></div>
    </aside></div>
    <section className="reasoning-workspace"><div className="panel reasoning-header"><div><p className="eyebrow">PHASE 3E / SCIENTIFIC REASONING</p><h2>Why the evidence points where it does.</h2><p className="muted-copy">The workspace keeps source evidence, explicit propositions, deterministic aggregation, uncertainty, and reproducibility visible. Confidence is a HelixMind evidence assessment, not scientific or clinical certainty.</p></div><div className="reasoning-metrics"><span><b>{investigation.health?.evidence ?? evidence.length}</b> evidence</span><span><b>{reasoning?.hypotheses ?? hypotheses.length}</b> hypotheses</span><span><b>{reasoning?.contradictions ?? contradictions.length}</b> contradictions</span><span><b>{reasoning?.knowledgeGaps ?? gaps.length}</b> open gaps</span></div></div>
      <section className="panel evidence-explorer"><div className="panel-heading"><div><p className="eyebrow">EVIDENCE EXPLORER</p><h2>Navigate source-linked findings</h2></div><span className="phase-note">{evidence.length} FILTERED</span></div><div className="evidence-filters"><label>Polarity<select value={evidencePolarity} onChange={event => setEvidencePolarity(event.target.value)}><option value="">All polarities</option><option value="SUPPORTS">Supports</option><option value="CONTRADICTS">Contradicts</option><option value="NEUTRAL">Neutral</option><option value="UNCERTAIN">Uncertain</option></select></label><label>Minimum confidence<select value={minimumConfidence} onChange={event => setMinimumConfidence(event.target.value)}><option value="">Any confidence</option><option value="0.35">35%+</option><option value="0.55">55%+</option><option value="0.75">75%+</option></select></label><span className="filter-note">Showing records with paper, source span, and source location provenance.</span></div>{evidence.length === 0 ? <p className="muted-copy">No evidence matches the current filters, or evidence extraction has not completed.</p> : <div className="evidence-list">{evidence.map(item => <article className="evidence-card" key={item.id}><div className="evidence-card-top"><span className={`evidence-polarity evidence-${(item.polarity || 'UNCERTAIN').toLowerCase()}`}>{item.polarity || 'UNCERTAIN'}</span>{item.paperId && <Link href={`/literature/${item.paperId}`}>Open source paper ↗</Link>}</div><p>{item.extractedText}</p><small>{item.sourceLocation} · extraction confidence {confidence(item.confidence)}{item.propositionId ? ` · proposition ${item.propositionId.slice(0, 8)}` : ' · no structured proposition'}</small></article>)}</div>}</section>
      <div className="reasoning-grid"><section className="panel"><p className="eyebrow">HYPOTHESES</p><h2>Evidence balance</h2>{hypotheses.length === 0 ? <p className="muted-copy">Hypotheses will appear after structured evidence is extracted.</p> : <div className="hypothesis-list">{hypotheses.map(item => <article className="hypothesis-card" key={item.id}><div className="hypothesis-top"><span className={`status-chip status-${item.status.toLowerCase()}`}>{item.status}</span><b>{confidence(item.confidence)} evidence confidence</b></div><h3>{item.statement}</h3><p className="paper-meta">{item.supportingEvidenceCount} supporting · {item.contradictoryEvidenceCount} contradictory · {item.proposition ? `${item.proposition.subject} ${item.proposition.predicate.toLowerCase()} ${item.proposition.object}` : 'No structured proposition'}</p>{item.supportingEvidence.length > 0 && <div className="linked-evidence"><small>Supporting evidence</small>{item.supportingEvidence.slice(0, 3).map(value => <p key={value.id}>{value.extractedText}</p>)}</div>}{item.contradictoryEvidence.length > 0 && <div className="linked-evidence linked-opposing"><small>Contradictory evidence</small>{item.contradictoryEvidence.slice(0, 3).map(value => <p key={value.id}>{value.extractedText}</p>)}</div>}</article>)}</div>}</section>
        <section className="panel"><p className="eyebrow">CONTRADICTIONS</p><h2>Opposing evidence</h2>{contradictions.length === 0 ? <p className="muted-copy">No contradictory evidence identified in the retrieved corpus.</p> : <div className="evidence-list">{contradictions.map(item => <article className="contradiction-card" key={item.id}><b>{item.proposition.description}</b><p><span>Supports:</span> {item.supportingEvidence.extractedText}</p><p><span>Contradicts:</span> {item.contradictoryEvidence.extractedText}</p><small>{item.contradictionType.toLowerCase()} contradiction · confidence {confidence(item.confidence)}</small></article>)}</div>}</section>
        <section className="panel"><p className="eyebrow">KNOWLEDGE GAPS</p><h2>What remains unknown</h2>{gaps.length === 0 ? <p className="muted-copy">No knowledge gaps have been derived yet.</p> : <div className="evidence-list">{gaps.map(item => <article className="gap-card" key={item.id}><span className="source-label">{item.severity} PRIORITY</span><p>{item.description}</p><small>{item.evidenceCount} evidence · {item.contradictionCount} contradictory · confidence {confidence(item.confidence)}</small>{item.researchOpportunity && <em>{item.researchOpportunity}</em>}</article>)}</div>}</section>
      </div>
      <section className="panel reasoning-trace"><p className="eyebrow">REASONING TRACE</p><h2>Inspectable inference</h2>{!reasoning?.items.length ? <p className="muted-copy">The deterministic reasoning trace will appear after the worker analyzes structured evidence.</p> : reasoning.items.map(item => <article className="trace-card" key={item.id}><div><b>{item.ruleName.replaceAll('_', ' ')}</b><span>{confidence(item.confidence)} evidence confidence</span></div><p>{item.reasoningSummary}</p>{item.trace.starting_proposition && <small>Proposition: {item.trace.starting_proposition.subject} {item.trace.starting_proposition.predicate.toLowerCase()} {item.trace.starting_proposition.object} · {item.trace.supporting_evidence?.length ?? 0} support / {item.trace.contradictory_evidence?.length ?? 0} contradiction</small>}</article>)}</section>
    </section>
  </>}</div></ProtectedShell>;
}
