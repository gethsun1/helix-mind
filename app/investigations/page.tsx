'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { ProtectedPage } from '../components/ProtectedPage';

type Investigation = { id: string; title: string; researchQuestion: string; domain: string; status: string; updatedAt: string };

export default function InvestigationsPage() {
  const [items, setItems] = useState<Investigation[]>([]);
  const [error, setError] = useState('');
  useEffect(() => { fetch('/api/backend/api/v1/investigations', { cache: 'no-store' }).then(async response => { if (!response.ok) throw new Error(); setItems(await response.json()); }).catch(() => setError('Investigation history could not be loaded.')); }, []);
  return <ProtectedPage eyebrow="RESEARCH / INVESTIGATIONS" title="Your investigations."><div className="panel"><div className="panel-heading"><div><p className="eyebrow">OWNER-SCOPED HISTORY</p><h2>Research queue</h2></div><span className="count">{items.length}</span></div>{error && <p className="error-text">{error}</p>}{!error && items.length === 0 ? <div className="empty-state"><span>∴</span><h3>No investigations yet.</h3><p>Start one from the dashboard.</p></div> : <div className="investigation-list">{items.map(item => <Link href={`/investigations/${item.id}`} key={item.id}><span className={`status-dot status-${item.status.toLowerCase()}`} /><div><b>{item.title}</b><small>{item.status.replaceAll('_', ' ')} · {item.domain}</small><em>{item.researchQuestion}</em></div><span>→</span></Link>)}</div>}</div></ProtectedPage>;
}
