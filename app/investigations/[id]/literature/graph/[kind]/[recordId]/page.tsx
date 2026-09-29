'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { ProtectedPage } from '../../../../../../components/ProtectedPage';

type Publication = { publicationId: string; title: string; source: string; counts: Record<string, number>; contributions: { evidence: { id: string; text: string; sourceLocation: string; sourceSpan: Record<string, number> | null }[] } };
type Result = { kind: string; recordId: string; publications: Publication[]; provenance: string };

export default function GraphPublicationSupportPage() {
  const { id, kind, recordId } = useParams<{ id: string; kind: string; recordId: string }>();
  const [data, setData] = useState<Result | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { fetch(`/api/backend/api/v1/investigations/${id}/literature/graph/${kind}/${recordId}/publications`, { cache: 'no-store' }).then(async response => { if (!response.ok) throw new Error(response.status === 404 ? 'Graph record not found in this investigation.' : 'Publication support could not be loaded.'); setData(await response.json()); }).catch(value => setError(value.message)); }, [id, kind, recordId]);
  return <ProtectedPage eyebrow={`INVESTIGATION / GRAPH / ${kind.toUpperCase()}`} title="Supporting publications."><div className="literature-page"><Link className="button button-ghost button-small" href={`/investigations/${id}/literature`}>← Literature landscape</Link>{error ? <div className="panel"><p className="error-text">{error}</p></div> : !data ? <div className="panel"><p>Loading graph provenance…</p></div> : <><p className="muted-copy">{data.provenance}</p>{data.publications.map(publication => <article className="paper-card" key={publication.publicationId}><div className="paper-card-top"><span className="source-label">{publication.source}</span></div><h3><Link href={`/investigations/${id}/literature/${publication.publicationId}`}>{publication.title}</Link></h3><p className="paper-meta">{publication.counts.evidence} evidence · {publication.counts.claims} claims · {publication.counts.relationships} relationships</p>{publication.contributions.evidence.map(evidence => <div className="evidence-card" key={evidence.id}><p>{evidence.text}</p><small>{evidence.sourceLocation}{evidence.sourceSpan ? ` · ${evidence.sourceSpan.start}–${evidence.sourceSpan.end}` : ''}</small></div>)}</article>)}{data.publications.length === 0 && <div className="panel empty-state"><h3>Limited publication support</h3><p>No retrieved publication with linked persisted evidence was found for this graph record.</p></div>}</>}</div></ProtectedPage>;
}
