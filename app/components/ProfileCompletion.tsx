'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';

type Profile = { name: string | null; role: string };

export function ProfileCompletion({ profile, onSaved }: { profile: Profile; onSaved: (profile: Profile) => void }) {
  const [displayName, setDisplayName] = useState(profile.name?.trim() ?? '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    const normalized = displayName.trim().replace(/\s+/g, ' ');
    if (normalized.length < 2) {
      setError('Enter at least two characters.');
      return;
    }
    setBusy(true);
    setError('');
    const response = await fetch('/api/backend/api/v1/me', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ displayName: normalized }),
    });
    if (!response.ok) {
      setError('Your profile could not be saved. Please try again.');
      setBusy(false);
      return;
    }
    onSaved(await response.json());
    setBusy(false);
  }

  return <div className="profile-overlay" role="presentation">
    <section className="profile-dialog" role="dialog" aria-modal="true" aria-labelledby="profile-completion-title">
      <p className="eyebrow">WELCOME TO HELIXMIND</p>
      <h2 id="profile-completion-title">Let&apos;s set up your researcher profile.</h2>
      <p>What should we call you?</p>
      <form onSubmit={save}>
        <label htmlFor="profile-display-name">Display name<input ref={inputRef} id="profile-display-name" value={displayName} onChange={event => setDisplayName(event.target.value)} autoComplete="name" maxLength={255} aria-describedby={error ? 'profile-completion-error' : undefined} /></label>
        {error && <p id="profile-completion-error" className="profile-error" role="alert">{error}</p>}
        <button className="button" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Continue'}</button>
      </form>
    </section>
  </div>;
}
