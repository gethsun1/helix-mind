'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { ProtectedShell } from '../../components/ProtectedShell';

type Event = { id: string; type: string; message: string; metadata: Record<string, unknown> | null; createdAt: string };
type Paper = { id: string; source: string; sourceRecords: string[]; title: string; abstract: string | null; authors: string[] | null; journal: string | null; publicationDate: string | null; doi: string | null; pmid: string | null; pmcid: string | null; url: string | null; relevanceScore: number | null; relevanceReason: string | null; sourceQuery: string | null; rank: number | null };
type PaperPage = { items: Paper[]; total: number; page: number; pageSize: number; pageCount: number };
type Search = { id: string; source: string; query: string; filters: Record<string, unknown> | null; executedAt: string; resultCount: number; status: string; errorMessage: string | null; reused: boolean };
type Investigation = { id: string; title: string; researchQuestion: string; domain: string; status: string; createdAt: string; updatedAt: string; startedAt: string | null; completedAt: string | null; errorMessage: string | null; researchPlan: Record<string, unknown> | null; events: Event[] };

const PLAN_FIELDS = ['research_objectives', 'research_questions', 'search_strategies', 'key_concepts', 'evidence_categories', 'reasoning_tasks'];
function pretty(value: string) { return value.replaceAll('_', ' '); }
function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'; }
function formatPaperDate(value: string | null) { return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value)) : 'Publication date unavailable'; }

export default function InvestigationPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [papers, setPapers] = useState<PaperPage | null>(null);
  const [searches, setSearches] = useState<Search[]>([]);
  const [paperPage, setPaperPage] = useState(1);
  const [source, setSource] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const query = new URLSearchParams({ page: String(paperPage), pageSize: '8' });
    if (source) query.set('source', source);
    const [investigationResponse, papersResponse, searchesResponse] = await Promise.all([
      fetch(`/api/backend/api/v1/investigations/${id}`, { cache: 'no-store' }),
      fetch(`/api/backend/api/v1/investigations/${id}/papers?${query}`, { cache: 'no-store' }),
      fetch(`/api/backend/api/v1/investigations/${id}/searches`, { cache: 'no-store' }),
    ]);
    if (!investigationResponse.ok) { setError(investigationResponse.status === 404 ? 'Investigation not found.' : 'Investigation could not be loaded.'); return; }
    setInvestigation(await investigationResponse.json());
    if (papersResponse.ok) setPapers(await papersResponse.json());
    if (searchesResponse.ok) setSearches(await searchesResponse.json());
    setError('');
  }, [id, paperPage, source]);

  useEffect(() => { void load(); const timer = window.setInterval(() => void load(), 5000); return () => window.clearInterval(timer); }, [load]);

  async function cancel() {
    setBusy(true); setError('');
    const response = await fetch(`/api/backend/api/v1/investigations/${id}/cancel`, { method: 'POST' });
    if (!response.ok) setError('This investigation could not be cancelled.');
    await load(); setBusy(false);
  }

  const planEntries = useMemo(() => PLAN_FIELDS.filter(key => Array.isArray(investigation?.researchPlan?.[key])), [investigation]);
  const sourceCounts = useMemo(() => papers?.items.reduce<Record<string, number>>((counts, paper) => { for (const item of paper.sourceRecords.length ? paper.sourceRecords : [paper.source]) counts[item] = (counts[item] || 0) + 1; return counts; }, {}) ?? {}, [papers]);
  const dedupEvent = investigation?.events.find(event => event.type === 'papers_deduplicated');
  const duplicatesRemoved = typeof dedupEvent?.metadata?.duplicates_removed === 'number' ? dedupEvent.metadata.duplicates_removed : 0;

  return <ProtectedShell><div className="page-wrap investigation-workspace">{error && !investigation ? <div className="panel"><p className="error-text">{error}</p></div> : !investigation ? <div className="panel"><p>Loading investigation…</p></div> : <>
    <p className="eyebrow">RESEARCH / INVESTIGATION</p>
    <div className="workspace-title"><div><span className={`status-chip status-${investigation.status.toLowerCase()}`}>{pretty(investigation.status)}</span><h1>{investigation.title}</h1><p className="workspace-question">{investigation.researchQuestion}</p><small className="mono">{investigation.domain} · created {formatDate(investigation.createdAt)}</small></div>{investigation.status.toUpperCase() === 'QUEUED' && <button className="button button-ghost" onClick={cancel} disabled={busy}>{busy ? 'Cancelling…' : 'Cancel investigation'}</button>}</div>
    {error && <p className="error-text">{error}</p>}
    <div className="workspace-grid"><section>
      <div className="panel literature-panel"><div className="panel-heading"><div><p className="eyebrow">LITERATURE</p><h2>Source-grounded papers</h2></div><span className="phase-note">Phase 3C</span></div><div className="literature-metrics"><div><b>{papers?.total ?? 0}</b><span>unique papers</span></div><div><b>{sourceCounts.PUBMED ?? 0}</b><span>PubMed records</span></div><div><b>{sourceCounts.EUROPE_PMC ?? 0}</b><span>Europe PMC records</span></div><div><b>{duplicatesRemoved}</b><span>duplicates removed</span></div></div>{papers && papers.items.length > 0 ? <><div className="paper-list">{papers.items.map(paper => <article className="paper-card" key={paper.id}><div className="paper-card-top"><span className="source-label">{paper.sourceRecords.join(' · ')}</span>{paper.relevanceScore !== null && <span className="relevance-label">Relevance {Math.round(paper.relevanceScore * 100)}%</span>}</div><h3><Link href={`/literature/${paper.id}`}>{paper.title}</Link></h3><p className="paper-meta">{paper.authors?.slice(0, 4).join(', ') || 'Author information unavailable'} · {paper.journal || 'Journal unavailable'} · {formatPaperDate(paper.publicationDate)}</p><p className="paper-abstract">{paper.abstract || 'Abstract unavailable from source.'}</p><div className="paper-card-bottom">{paper.pmid && <span>PMID {paper.pmid}</span>}{paper.doi && <span>DOI {paper.doi}</span>}{paper.url && <a href={paper.url} target="_blank" rel="noreferrer">Original source ↗</a>}</div></article>)}</div><div className="pagination"><button className="button button-ghost button-small" disabled={paperPage <= 1} onClick={() => setPaperPage(value => value - 1)}>← Previous</button><span>Page {papers.page} of {papers.pageCount}</span><button className="button button-ghost button-small" disabled={paperPage >= papers.pageCount} onClick={() => setPaperPage(value => value + 1)}>Next →</button></div></> : <div className="plan-empty"><span>∴</span><p>{investigation.status.toUpperCase() === 'SEARCHING' ? 'Literature sources are being queried.' : 'No papers were returned by the available sources.'}</p></div>}<p className="phase-disclaimer">Relevance is a transparent ordering signal based on plan-concept overlap and recency. It is not scientific evidence strength.</p></div>
      <div className="panel"><div className="panel-heading"><div><p className="eyebrow">OMEGACLAW PLAN</p><h2>Research strategy</h2></div></div>{investigation.researchPlan && planEntries.length > 0 ? <div className="plan-grid">{planEntries.map(key => <div className="plan-block" key={key}><h3>{pretty(key)}</h3><ul>{(investigation.researchPlan?.[key] as string[]).map((item, index) => <li key={`${key}-${index}`}>{item}</li>)}</ul></div>)}</div> : <div className="plan-empty"><span>∴</span><p>{investigation.status.toUpperCase() === 'FAILED' ? investigation.errorMessage : 'OmegaClaw is preparing the structured research plan.'}</p></div>}<p className="phase-disclaimer">Scientific claims and evidence reasoning are intentionally deferred to later phases.</p></div>
    </section><aside>
      <div className="panel event-panel"><p className="eyebrow">AUDIT TRAIL</p><h2>Processing events</h2><div className="timeline">{investigation.events.map(event => <div className="timeline-item" key={event.id}><span className="timeline-marker" /><div><b>{pretty(event.type)}</b><p>{event.message}</p><small>{formatDate(event.createdAt)}</small></div></div>)}</div></div>
      <div className="panel search-panel"><p className="eyebrow">REPRODUCIBILITY</p><h2>Searches executed</h2>{searches.length === 0 ? <p className="muted-copy">Source searches will appear here after the worker starts.</p> : <div className="search-list">{searches.map(search => <div className="search-record" key={search.id}><div><b>{search.source}</b><small>{search.status}{search.reused ? ' · reused' : ''} · {search.resultCount} records</small></div><code>{search.query}</code><small>{formatDate(search.executedAt)}</small></div>)}</div>}</div>
      <div className="panel"><label className="filter-label">PAPER SOURCE<select value={source} onChange={event => { setSource(event.target.value); setPaperPage(1); }}><option value="">All sources</option><option value="PUBMED">PubMed</option><option value="EUROPE_PMC">Europe PMC</option></select></label></div>
    </aside></div>
  </>}</div></ProtectedShell>;
}
