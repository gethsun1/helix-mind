'use client';

import Link from 'next/link';
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import { ProtectedShell } from '../components/ProtectedShell';

type User = { name: string | null; email: string; role: string; image: string | null };
type Investigation = { id: string; title: string; researchQuestion: string; domain: string; status: string; createdAt: string };
const ACTIVE_STATUSES = new Set(['QUEUED', 'PLANNING', 'SEARCHING', 'KNOWLEDGE', 'REASONING']);
const TOUR_STEPS = [
  { target: 'title', title: 'Name your research project', description: 'Enter a short project title. For example: “Evidence review — CRISPR-Cas9 and sickle cell disease”.' },
  { target: 'domain', title: 'Choose a research domain', description: 'Pick the domain that best describes your question. This helps organize the investigation.' },
  { target: 'question', title: 'Write the research question', description: 'Ask a focused, answerable question. For example: “What clinical evidence supports CRISPR-Cas9 therapies for sickle cell disease, and what safety outcomes have been reported?”' },
  { target: 'submit', title: 'Queue your investigation', description: 'After you complete this tour, select Queue investigation to start. HelixMind will plan the search, retrieve literature, and build source-linked research records.' },
] as const;
const TOUR_STORAGE_PREFIX = 'helixmind:dashboard-tour:v1:';
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
  const [tourStep, setTourStep] = useState<number | null>(null);
  const [tourPlacement, setTourPlacement] = useState<'top' | 'bottom'>('bottom');
  const tourDialogRef = useRef<HTMLElement>(null);

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

  const closeTour = useCallback((result: 'dismissed' | 'completed' = 'dismissed') => {
    if (user) {
      try { window.localStorage.setItem(`${TOUR_STORAGE_PREFIX}${user.email.toLowerCase()}`, result); } catch { /* Storage is optional. */ }
    }
    setTourStep(null);
  }, [user]);

  useEffect(() => {
    if (userLoading || !user) return;
    try {
      if (!window.localStorage.getItem(`${TOUR_STORAGE_PREFIX}${user.email.toLowerCase()}`)) setTourStep(0);
    } catch {
      // The dashboard tour remains available from its button when storage is disabled.
    }
  }, [userLoading, user]);

  useEffect(() => {
    if (tourStep === null) return;
    const step = TOUR_STEPS[tourStep];
    const target = document.querySelector<HTMLElement>(`[data-tour-target="${step.target}"]`);
    if (!target) return;
    target.classList.add('tour-highlight');
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    tourDialogRef.current?.focus();

    let frame = 0;
    const updatePlacement = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const rect = target.getBoundingClientRect();
        setTourPlacement(rect.top + rect.height / 2 > window.innerHeight * 0.55 ? 'top' : 'bottom');
      });
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeTour();
    };
    updatePlacement();
    window.addEventListener('scroll', updatePlacement, { passive: true });
    window.addEventListener('resize', updatePlacement);
    window.addEventListener('keydown', onKeyDown);
    return () => {
      cancelAnimationFrame(frame);
      target.classList.remove('tour-highlight');
      window.removeEventListener('scroll', updatePlacement);
      window.removeEventListener('resize', updatePlacement);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [tourStep, closeTour]);

  function advanceTour() {
    if (tourStep === null) return;
    if (tourStep === TOUR_STEPS.length - 1) closeTour('completed');
    else setTourStep(tourStep + 1);
  }

  const metrics = useMemo(() => ({
    total: investigations.length,
    active: investigations.filter(item => ACTIVE_STATUSES.has(item.status.toUpperCase())).length,
    completed: investigations.filter(item => item.status.toUpperCase() === 'COMPLETED').length,
    failed: investigations.filter(item => item.status.toUpperCase() === 'FAILED').length,
  }), [investigations]);

  async function create(event: FormEvent) {
    event.preventDefault();
    if (tourStep !== null) return;
    setBusy(true); setError('');
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
      <section className="panel new-investigation"><div className="dashboard-form-heading"><p className="eyebrow">RESEARCH PROJECT / INVESTIGATION</p><button className="button button-ghost button-small" type="button" onClick={() => setTourStep(0)}>Take a quick tour</button></div><h2>What research question should this project examine?</h2><p>A bounded OmegaClaw planning agent structures the approach, then the research workflow retrieves literature and builds source-linked evidence and deterministic reasoning.</p><form onSubmit={create}><label data-tour-target="title">Research project title<input value={title} onChange={event => setTitle(event.target.value)} maxLength={255} placeholder="e.g. Evidence review — CRISPR-Cas9 and sickle cell disease" /></label><label data-tour-target="domain">Research domain<select value={domain} onChange={event => setDomain(event.target.value)}><option value="biotechnology">Biotechnology</option><option value="medicine">Medicine</option><option value="climate">Climate science</option><option value="materials">Materials science</option><option value="other">Other</option></select></label><label data-tour-target="question">Research question<textarea value={researchQuestion} onChange={event => setResearchQuestion(event.target.value)} minLength={10} maxLength={5000} required placeholder="What clinical evidence supports CRISPR-Cas9 therapies for sickle cell disease, and what safety outcomes have been reported?" /></label><button data-tour-target="submit" className="button" disabled={busy || tourStep !== null}>{busy ? 'Queueing…' : 'Queue investigation ↗'}</button></form>{error && <p className="error-text">{error}</p>}</section>
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">YOUR RESEARCH</p><h2>Recent investigations</h2></div><span className="count">{investigations.length}</span></div>{investigations.length === 0 ? <div className="empty-state"><span>∴</span><h3>No investigations yet.</h3><p>Start your first scientific investigation to build a traceable research history.</p></div> : <div className="investigation-list">{investigations.slice(0, 8).map(item => <Link href={`/investigations/${item.id}`} key={item.id}><span className={`status-dot status-${item.status.toLowerCase()}`} /><div><b>{item.title}</b><small>{statusLabel(item.status)} · {item.domain}</small><em>{item.researchQuestion}</em></div><span>→</span></Link>)}</div>}</section>
    </div>
  </div>{tourStep !== null && <><div className="onboarding-backdrop" aria-hidden="true" /><section className={`onboarding-card onboarding-card-${tourPlacement}`} role="dialog" aria-labelledby="onboarding-title" aria-describedby="onboarding-description" tabIndex={-1} ref={tourDialogRef}><p className="eyebrow">QUICK TOUR · STEP {tourStep + 1} OF {TOUR_STEPS.length}</p><h2 id="onboarding-title">{TOUR_STEPS[tourStep].title}</h2><p id="onboarding-description">{TOUR_STEPS[tourStep].description}</p><div className="onboarding-actions"><button className="button button-ghost button-small" type="button" onClick={() => setTourStep(Math.max(0, tourStep - 1))} disabled={tourStep === 0}>Back</button><button className="button button-ghost button-small" type="button" onClick={() => closeTour()}>Exit</button><button className="button button-small" type="button" onClick={advanceTour}>{tourStep === TOUR_STEPS.length - 1 ? 'Complete' : 'Next'}</button></div></section></>}</ProtectedShell>;
}
