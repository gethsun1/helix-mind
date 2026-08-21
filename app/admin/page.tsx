'use client';

import { useEffect, useState } from 'react';
import { ProtectedPage } from '../components/ProtectedPage';

export default function AdminPage() {
  const [diagnostics, setDiagnostics] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { fetch('/api/backend/api/v1/admin/diagnostics').then(response => response.ok ? response.json() : null).then(setDiagnostics); }, []);
  return <ProtectedPage eyebrow="SYSTEM / ADMINISTRATION" title="System diagnostics." admin><div className="diagnostics-grid">{diagnostics ? Object.entries(diagnostics).map(([key, value]) => <div className="panel" key={key}><p className="eyebrow">{key.replaceAll('_', ' ')}</p><pre>{JSON.stringify(value, null, 2)}</pre></div>) : <div className="panel"><p>Loading redacted diagnostics…</p></div>}</div><p className="privacy-note">Diagnostic output intentionally excludes credentials, environment values, database passwords and session secrets.</p></ProtectedPage>;
}
