'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState } from 'react';

import { ProtectedShell } from '../components/ProtectedShell';

type User = { name: string | null; email: string; role: string; image: string | null };
type Investigation = { id: string; question: string; status: string };

export default function DashboardPage() {
  const [user, setUser] = useState<User | null>(null);
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [question, setQuestion] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    const [meResponse, investigationsResponse] = await Promise.all([
      fetch('/api/backend/api/v1/me', { cache: 'no-store' }),
      fetch('/api/backend/api/v1/investigations', { cache: 'no-store' }),
    ]);
    if (meResponse.ok) setUser(await meResponse.json());
    if (investigationsResponse.ok) setInvestigations(await investigationsResponse.json());
  }
  useEffect(() => { void load(); }, []);

  async function create(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    const response = await fetch('/api/backend/api/v1/investigations', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) });
    if (!response.ok) { setError('The investigation could not be queued.'); setBusy(false); return; }
    setQuestion(''); setBusy(false); await load();
  }

  return <ProtectedShell admin={user?.role === 'ADMIN'}><div className="page-wrap"><p className="eyebrow">HELIXMIND / DASHBOARD</p><div className="dashboard-heading"><div><h1>{user?.name ? `Welcome, ${user.name.split(' ')[0]}.` : 'Your research workspace.'}</h1><p>Questions, evidence and reasoning that belong to your account.</p></div><span className="role-pill">{user?.role ?? 'USER'}</span></div><div className="dashboard-grid"><section className="panel new-investigation"><p className="eyebrow">START WITH A QUESTION</p><h2>What would you like to investigate?</h2><p>OmegaClaw will queue the question for the research workflow. Processing remains asynchronous and source-grounded.</p><form onSubmit={create}><textarea value={question} onChange={event => setQuestion(event.target.value)} minLength={10} maxLength={5000} required placeholder="e.g. What is the current evidence for CRISPR-based therapeutic approaches to sickle-cell disease?" /><button className="button" disabled={busy}>{busy ? 'Queueing…' : 'Queue investigation ↗'}</button></form>{error && <p className="error-text">{error}</p>}</section><section className="panel"><div className="panel-heading"><div><p className="eyebrow">YOUR RESEARCH</p><h2>Investigations</h2></div><span className="count">{investigations.length}</span></div>{investigations.length === 0 ? <div className="empty-state"><span>∴</span><h3>No investigations yet.</h3><p>Start your first scientific investigation to build a traceable research history.</p></div> : <div className="investigation-list">{investigations.map(item => <Link href={`/investigations/${item.id}`} key={item.id}><span className="status-dot" /><div><b>{item.question}</b><small>{item.status.replaceAll('_', ' ')}</small></div><span>→</span></Link>)}</div>}</section></div></div></ProtectedShell>;
}
