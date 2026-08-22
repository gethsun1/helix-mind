'use client';

import { useParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { ProtectedShell } from '../../components/ProtectedShell';

type Event = { id: string; type: string; message: string; metadata: Record<string, unknown> | null; createdAt: string };
type Investigation = { id: string; title: string; researchQuestion: string; domain: string; status: string; createdAt: string; updatedAt: string; startedAt: string | null; completedAt: string | null; errorMessage: string | null; researchPlan: Record<string, unknown> | null; events: Event[] };
const PLAN_FIELDS = ['research_objectives', 'research_questions', 'search_strategies', 'key_concepts', 'evidence_categories', 'reasoning_tasks'];
function pretty(value: string) { return value.replaceAll('_', ' '); }
function date(value: string | null) { return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'; }

export default function InvestigationPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    const response = await fetch(`/api/backend/api/v1/investigations/${id}`, { cache: 'no-store' });
    if (!response.ok) { setError(response.status === 404 ? 'Investigation not found.' : 'Investigation could not be loaded.'); return; }
    setInvestigation(await response.json()); setError('');
  }, [id]);
  useEffect(() => { void load(); const timer = window.setInterval(() => void load(), 5000); return () => window.clearInterval(timer); }, [load]);
  async function cancel() { setBusy(true); setError(''); const response = await fetch(`/api/backend/api/v1/investigations/${id}/cancel`, { method: 'POST' }); if (!response.ok) setError('This investigation could not be cancelled.'); await load(); setBusy(false); }
  const planEntries = useMemo(() => PLAN_FIELDS.filter(key => Array.isArray(investigation?.researchPlan?.[key])), [investigation]);
  return <ProtectedShell><div className="page-wrap investigation-workspace">{error && !investigation ? <div className="panel"><p className="error-text">{error}</p></div> : !investigation ? <div className="panel"><p>Loading investigation…</p></div> : <><p className="eyebrow">RESEARCH / INVESTIGATION</p><div className="workspace-title"><div><span className={`status-chip status-${investigation.status.toLowerCase()}`}>{pretty(investigation.status)}</span><h1>{investigation.title}</h1><p className="workspace-question">{investigation.researchQuestion}</p><small className="mono">{investigation.domain} · created {date(investigation.createdAt)}</small></div>{investigation.status.toUpperCase() === 'QUEUED' && <button className="button button-ghost" onClick={cancel} disabled={busy}>{busy ? 'Cancelling…' : 'Cancel investigation'}</button>}</div>{error && <p className="error-text">{error}</p>}<div className="workspace-grid"><section><div className="panel"><div className="panel-heading"><div><p className="eyebrow">OMEGACLAW PLAN</p><h2>Research strategy</h2></div><span className="phase-note">Phase 3B</span></div>{investigation.researchPlan && planEntries.length > 0 ? <div className="plan-grid">{planEntries.map(key => <div className="plan-block" key={key}><h3>{pretty(key)}</h3><ul>{(investigation.researchPlan?.[key] as string[]).map((item, index) => <li key={`${key}-${index}`}>{item}</li>)}</ul></div>)}</div> : <div className="plan-empty"><span>∴</span><p>{investigation.status.toUpperCase() === 'FAILED' ? investigation.errorMessage : 'OmegaClaw is preparing the structured research plan.'}</p></div>}<p className="phase-disclaimer">Literature analysis will begin in Phase 3C. No scientific literature has been retrieved in this phase.</p></div></section><aside className="panel event-panel"><p className="eyebrow">AUDIT TRAIL</p><h2>Processing events</h2><div className="timeline">{investigation.events.map(event => <div className="timeline-item" key={event.id}><span className="timeline-marker" /><div><b>{pretty(event.type)}</b><p>{event.message}</p><small>{date(event.createdAt)}</small></div></div>)}</div></aside></div></>}</div></ProtectedShell>;
}
