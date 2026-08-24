'use client';

import { useEffect, useMemo, useState } from 'react';
import { ProtectedPage } from '../components/ProtectedPage';

type Investigation = { id: string; title: string };
type Node = { id: string; type: string; label: string; entityType: string; aliases: string[] };
type Edge = { id: string; source: string; target: string; relationship: string; stance: string; claims: { id: string; text: string; paperId: string; paperTitle: string | null }[] };
type Summary = { entities: number; claims: number; evidence: number; relationships: number; graph: { nodes: Node[]; edges: Edge[] } };

export default function KnowledgePage() {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [investigationId, setInvestigationId] = useState('');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [query, setQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => { fetch('/api/backend/api/v1/investigations', { cache: 'no-store' }).then(async response => { if (!response.ok) throw new Error('Investigations could not be loaded.'); const items = await response.json(); setInvestigations(items); setInvestigationId(items[0]?.id ?? ''); }).catch(value => setError(value.message)).finally(() => setLoading(false)); }, []);
  useEffect(() => { if (!investigationId) { setSummary(null); return; } setLoading(true); const params = new URLSearchParams({ limit: '200' }); if (query.trim()) params.set('q', query.trim()); fetch(`/api/backend/api/v1/investigations/${investigationId}/knowledge?${params}`, { cache: 'no-store' }).then(async response => { if (!response.ok) throw new Error('Knowledge graph could not be loaded.'); setSummary(await response.json()); setError(''); }).catch(value => setError(value.message)).finally(() => setLoading(false)); }, [investigationId, query]);

  const dimensions = useMemo(() => ({ width: Math.max(900, Math.min(1200, 180 * Math.min(4, summary?.graph.nodes.length ?? 1))), height: 160 + Math.ceil((summary?.graph.nodes.length ?? 1) / 4) * 125 }), [summary]);
  const positions = useMemo(() => new Map((summary?.graph.nodes ?? []).map((node, index) => [node.id, { x: 90 + (index % 4) * 180, y: 80 + Math.floor(index / 4) * 125, node }])), [summary]);
  const selectedInvestigation = investigations.find(item => item.id === investigationId);

  return <ProtectedPage eyebrow="RESEARCH / KNOWLEDGE GRAPH" title="Knowledge graph.">
    <div className="knowledge-toolbar panel"><div><p className="eyebrow">PROVENANCE-PRESERVING KNOWLEDGE</p><p className="muted-copy">Only entities, claims, and explicit relationships extracted from your retrieved literature appear here.</p></div><label className="filter-label">Investigation<select value={investigationId} onChange={event => { setInvestigationId(event.target.value); setSelectedNode(null); setSelectedEdge(null); }}><option value="">Choose an investigation</option>{investigations.map(item => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label><label className="filter-label">Search entities<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Filter by name" /></label></div>
    {error ? <div className="panel"><p className="error-text">{error}</p></div> : loading ? <div className="panel"><p>Loading knowledge…</p></div> : !selectedInvestigation ? <div className="panel empty-state"><span>∴</span><h3>Choose an investigation.</h3><p>Knowledge is scoped to the investigations you are authorized to access.</p></div> : !summary || summary.entities === 0 ? <div className="panel empty-state"><span>∴</span><h3>No source-grounded knowledge yet.</h3><p>Run an investigation with retrieved abstracts to create auditable entities and claims.</p></div> : <>
      <div className="metric-grid"><div className="metric-card"><span>Entities</span><b>{summary.entities}</b></div><div className="metric-card"><span>Claims</span><b>{summary.claims}</b></div><div className="metric-card"><span>Evidence records</span><b>{summary.evidence}</b></div><div className="metric-card"><span>Relationships</span><b>{summary.relationships}</b></div></div>
      <div className="knowledge-layout"><section className="panel knowledge-graph-panel"><div className="panel-heading"><div><p className="eyebrow">{selectedInvestigation.title}</p><h2>Inspectable graph</h2></div><span className="phase-note">SOURCE-GROUNDED</span></div><div className="knowledge-graph-scroll"><svg viewBox={`0 0 ${dimensions.width} ${dimensions.height}`} role="img" aria-label="Source-grounded scientific knowledge graph">{summary.graph.edges.map(edge => { const source = positions.get(edge.source); const target = positions.get(edge.target); return source && target ? <g key={edge.id} onClick={() => { setSelectedEdge(edge); setSelectedNode(null); }} className="knowledge-edge"><line x1={source.x} y1={source.y} x2={target.x} y2={target.y} /><text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 - 8}>{edge.relationship}</text></g> : null; })}{summary.graph.nodes.map(node => { const position = positions.get(node.id); return position ? <g key={node.id} onClick={() => { setSelectedNode(node); setSelectedEdge(null); }} className="knowledge-node"><circle cx={position.x} cy={position.y} r="30" /><text x={position.x} y={position.y + 52} textAnchor="middle">{node.label.slice(0, 22)}</text><text x={position.x} y={position.y + 67} textAnchor="middle" className="knowledge-node-type">{node.entityType}</text></g> : null; })}</svg></div></section><aside className="panel knowledge-inspector"><p className="eyebrow">INSPECTOR</p>{selectedNode ? <><h2>{selectedNode.label}</h2><p className="paper-meta">{selectedNode.entityType}</p><p className="muted-copy">Aliases: {selectedNode.aliases.length ? selectedNode.aliases.join(', ') : 'None recorded'}</p><p className="muted-copy">Select a relationship to inspect its supporting claim and paper.</p></> : selectedEdge ? <><h2>{selectedEdge.relationship}</h2><p className="paper-meta">{selectedEdge.stance}</p>{selectedEdge.claims.length ? selectedEdge.claims.map(claim => <div className="query-callout" key={claim.id}><span>Source-grounded claim</span><p>{claim.text}</p><small>{claim.paperTitle || 'Paper title unavailable'}</small></div>) : <p className="muted-copy">No supporting claim was returned.</p>}</> : <p className="muted-copy">Select an entity or relationship to inspect provenance.</p>}</aside></div>
    </>}
  </ProtectedPage>;
}
