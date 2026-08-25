'use client';

import { useEffect, useState } from 'react';

import { ProtectedPage } from '../components/ProtectedPage';

type Investigation = { id: string; title: string };
type Proposition = { subject: string; predicate: string; object: string };
type Hypothesis = { id: string; proposition: Proposition | null; statement: string; status: string; confidence: number; supportingEvidenceCount: number; contradictoryEvidenceCount: number };

export default function HypothesesPage() {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [investigationId, setInvestigationId] = useState('');
  const [items, setItems] = useState<Hypothesis[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch('/api/backend/api/v1/investigations', { cache: 'no-store' }).then(async response => { if (!response.ok) throw new Error('Investigations could not be loaded.'); const values = await response.json(); setInvestigations(values); setInvestigationId(values[0]?.id ?? ''); }).catch(value => setError(value.message));
  }, []);
  useEffect(() => {
    if (!investigationId) { setItems([]); return; }
    fetch(`/api/backend/api/v1/investigations/${investigationId}/hypotheses`, { cache: 'no-store' }).then(async response => { if (!response.ok) throw new Error('Hypotheses could not be loaded.'); setItems(await response.json()); setError(''); }).catch(value => setError(value.message));
  }, [investigationId]);

  return <ProtectedPage eyebrow="RESEARCH / HYPOTHESIS LAB" title="Hypothesis lab.">
    <div className="knowledge-toolbar panel"><div><p className="eyebrow">QUALIFIED EVIDENCE STATES</p><p className="muted-copy">Hypotheses summarize source-linked propositions. Status and confidence describe the retrieved evidence, not scientific certainty.</p></div><label className="filter-label">Investigation<select value={investigationId} onChange={event => setInvestigationId(event.target.value)}><option value="">Choose an investigation</option>{investigations.map(item => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label></div>
    {error ? <div className="panel"><p className="error-text">{error}</p></div> : !investigationId ? <div className="panel empty-state"><span>∴</span><h3>Choose an investigation.</h3><p>Hypotheses are owner-scoped to their source literature.</p></div> : items.length === 0 ? <div className="panel empty-state"><span>∴</span><h3>No structured hypotheses yet.</h3><p>Run an investigation with source abstracts to populate the reasoning layer.</p></div> : <div className="panel"><div className="hypothesis-list">{items.map(item => <article className="hypothesis-card" key={item.id}><div className="hypothesis-top"><span className={`status-chip status-${item.status.toLowerCase()}`}>{item.status}</span><b>{Math.round(item.confidence * 100)}% evidence confidence</b></div><h2>{item.statement}</h2><p className="paper-meta">{item.supportingEvidenceCount} supporting · {item.contradictoryEvidenceCount} contradictory</p>{item.proposition && <p className="muted-copy">Structured proposition: {item.proposition.subject} {item.proposition.predicate.toLowerCase()} {item.proposition.object}</p>}</article>)}</div></div>}
  </ProtectedPage>;
}
