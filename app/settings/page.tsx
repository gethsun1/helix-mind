'use client';

import { FormEvent, useEffect, useState } from 'react';

import { ProtectedPage } from '../components/ProtectedPage';

type User = { name: string | null; email: string; role: string };

export default function SettingsPage() {
  const [user, setUser] = useState<User | null>(null);
  const [displayName, setDisplayName] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch('/api/backend/api/v1/me', { cache: 'no-store' })
      .then(async response => { if (!response.ok) throw new Error(); return response.json(); })
      .then(value => { setUser(value); setDisplayName(value.name ?? ''); })
      .catch(() => setError('Your profile could not be loaded.'));
  }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setStatus('');
    setError('');
    const response = await fetch('/api/backend/api/v1/me', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ displayName: displayName.trim().replace(/\s+/g, ' ') }),
    });
    if (!response.ok) {
      setError('The display name could not be saved.');
      setBusy(false);
      return;
    }
    const updated = await response.json();
    setUser(updated);
    setDisplayName(updated.name ?? '');
    setStatus('Profile saved.');
    window.dispatchEvent(new CustomEvent('helixmind-profile-updated', { detail: updated }));
    setBusy(false);
  }

  return <ProtectedPage eyebrow="WORKSPACE / SETTINGS" title="Researcher profile."><div className="panel profile-form"><p>Keep your researcher identity up to date. Your role, email, account ID and investigation ownership are managed by HelixMind.</p><form onSubmit={save}><label htmlFor="settings-display-name">Display name<input id="settings-display-name" value={displayName} onChange={event => setDisplayName(event.target.value)} minLength={2} maxLength={255} required autoComplete="name" /></label><button className="button" type="submit" disabled={busy || !user}>{busy ? 'Saving…' : 'Save display name'}</button>{status && <p className="success-text" role="status">{status}</p>}{error && <p className="error-text" role="alert">{error}</p>}</form><div className="profile-meta"><div><span>Email</span><strong>{user?.email ?? 'Loading…'}</strong></div><div><span>Role</span><strong>{user?.role ?? 'Loading…'}</strong></div></div></div></ProtectedPage>;
}
