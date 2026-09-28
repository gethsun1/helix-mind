'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

import { ProtectedShell } from '../components/ProtectedShell';

type User = { name: string | null; email: string; role: string; image: string | null };
type Investigation = { id: string; title: string; researchQuestion: string; domain: string; status: string; createdAt: string };
const ACTIVE_STATUSES = new Set(['QUEUED', 'PLANNING', 'SEARCHING', 'KNOWLEDGE', 'REASONING']);
function statusLabel(status: string) { return status.replaceAll('_', ' ').toLowerCase(); }

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [title, setTitle] = useState('');
  const [domain, setDomain] = useState('biotechnology');
  const [researchQuestion, setResearchQuestion] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [userLoading, setUserLoading] = useState(true);

  async function load() {
    const [meResponse, investigationsResponse] = await Promise.all([
      fetch('/api/backend/api/v1/me', { cache: 'no-store' }),
      fetch('/api/backend/api/v1/investigations', { cache: 'no-store' }),
    ]);
    if (meResponse.ok) setUser(await meResponse.json());
    if (investigationsResponse.ok) setInvestigations(await investigationsResponse.json());
    setUserLoading(false);
  }
  useEffect(() => { void load(); }, []);

  const metrics = useMemo(() => ({
    total: investigations.length,
    active: investigations.filter(item => ACTIVE_STATUSES.has(item.status.toUpperCase())).length,
    completed: investigations.filter(item => item.status.toUpperCase() === 'COMPLETED').length,
    failed: investigations.filter(item => item.status.toUpperCase() === 'FAILED').length,
  }), [investigations]);

  async function create(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    const response = await fetch('/api/backend/api/v1/investigations', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: title || 'Scientific investigation', domain, researchQuestion }),
    });
    if (!response.ok) { setError('The investigation could not be queued.'); setBusy(false); return; }
    const created = await response.json(); setBusy(false); router.push(`/investigations/${created.id}`);
  }

  return <ProtectedShell admin={user?.role === 'ADMIN'}><div className="page-wrap">
    <p className="eyebrow">RESEARCH &amp; INNOVATION / WORKSPACE</p>
    <div className="dashboard-heading"><div><h1>{user?.name ? `${user.name.split(' ')[0]}, welcome to your research workspace.` : 'Welcome to your research workspace.'}</h1><p>Questions, evidence and reasoning that belong to your account.</p></div>{userLoading ? <span className="role-pill role-loading">Loading</span> : user && <span className="role-pill">{user.role}</span>}</div>
    <div className="metric-grid"><div className="metric-card"><span>Total investigations</span><b>{metrics.total}</b></div><div className="metric-card"><span>In progress</span><b>{metrics.active}</b></div><div className="metric-card"><span>Completed runs</span><b>{metrics.completed}</b></div><div className="metric-card"><span>Failed</span><b>{metrics.failed}</b></div></div>
    <div className="dashboard-grid">
      <section className="panel new-investigation"><p className="eyebrow">RESEARCH PROJECT / INVESTIGATION</p><h2>What research question should this project examine?</h2><p>A bounded OmegaClaw planning agent structures the approach, then the research workflow retrieves literature and builds source-linked evidence and deterministic reasoning.</p><form onSubmit={create}><label>Research project title<input value={title} onChange={event => setTitle(event.target.value)} maxLength={255} placeholder="e.g. Evidence review — CRISPR-Cas9 and sickle cell disease" /></label><label>Research domain<select value={domain} onChange={event => setDomain(event.target.value)}><option value="biotechnology">Biotechnology</option><option value="medicine">Medicine</option><option value="climate">Climate science</option><option value="materials">Materials science</option><option value="other">Other</option></select></label><label>Research question<textarea value={researchQuestion} onChange={event => setResearchQuestion(event.target.value)} minLength={10} maxLength={5000} required placeholder="What clinical evidence supports CRISPR-Cas9 therapies for sickle cell disease, and what safety outcomes have been reported?" /></label><button className="button" disabled={busy}>{busy ? 'Queueing…' : 'Queue investigation ↗'}</button></form>{error && <p className="error-text">{error}</p>}</section>
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">YOUR RESEARCH</p><h2>Recent investigations</h2></div><span className="count">{investigations.length}</span></div>{investigations.length === 0 ? <div className="empty-state"><span>∴</span><h3>No investigations yet.</h3><p>Start your first scientific investigation to build a traceable research history.</p></div> : <div className="investigation-list">{investigations.slice(0, 8).map(item => <Link href={`/investigations/${item.id}`} key={item.id}><span className={`status-dot status-${item.status.toLowerCase()}`} /><div><b>{item.title}</b><small>{statusLabel(item.status)} · {item.domain}</small><em>{item.researchQuestion}</em></div><span>→</span></Link>)}</div>}</section>
    </div>
  </div></ProtectedShell>;
}
