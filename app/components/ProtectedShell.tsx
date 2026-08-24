'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';

import { Brand } from './Brand';
import { ProfileCompletion } from './ProfileCompletion';
import { SignOutButton } from './SignOutButton';

const links = [
  ['/dashboard', 'Dashboard'],
  ['/investigations', 'Investigations'],
  ['/literature', 'Literature'],
  ['/knowledge', 'Knowledge Graph'],
  ['/hypotheses', 'Hypothesis Lab'],
  ['/settings', 'Settings'],
] as const;

export function ProtectedShell({ children, admin = false }: { children: React.ReactNode; admin?: boolean }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const [profile, setProfile] = useState<{ name: string | null; role: string } | null>(null);

  useEffect(() => { setMenuOpen(false); }, [pathname]);
  useEffect(() => {
    fetch('/api/backend/api/v1/me', { cache: 'no-store' })
      .then(response => response.ok ? response.json() : null)
      .then(user => { if (user) setProfile(user); })
      .catch(() => undefined);
  }, [pathname]);
  useEffect(() => {
    function update(event: Event) { setProfile((event as CustomEvent<{ name: string | null; role: string }>).detail); }
    window.addEventListener('helixmind-profile-updated', update);
    return () => window.removeEventListener('helixmind-profile-updated', update);
  }, []);

  const navigation = [...links, ...(profile?.role === 'ADMIN' ? [['/admin', 'System Diagnostics'] as const] : [])];

  return <div className="app-shell">
    <aside className={`sidebar${menuOpen ? ' sidebar-open' : ''}`} aria-label="Research workspace navigation">
      <div className="drawer-header"><Brand /><button className="drawer-close" type="button" onClick={() => setMenuOpen(false)} aria-label="Close navigation">×</button></div>
      <div className="sidebar-label">RESEARCH WORKSPACE</div>
      <nav>{navigation.map(([href, label]) => <Link href={href} key={href} className={pathname === href || (href !== '/dashboard' && pathname.startsWith(`${href}/`)) ? 'active' : ''}>{label}</Link>)}</nav>
      <div className="sidebar-foot"><span className="status-dot" /> HelixMind services isolated</div>
      <SignOutButton />
    </aside>
    {menuOpen && <button className="nav-backdrop" type="button" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
    <main className="workspace">
      <header className="workspace-header">
        <div className="mobile-workspace-header"><button className="menu-toggle" type="button" onClick={() => setMenuOpen(true)} aria-label="Open navigation" aria-expanded={menuOpen}>☰</button><Link href="/dashboard" className="mobile-brand"><span>Ω</span><strong>HelixMind</strong></Link></div>
        <span className="mono desktop-workspace-label">HELIXMIND / WORKSPACE</span>
        <Link href="/" className="back-link">Public overview ↗</Link>
      </header>
      {children}
    </main>
    {profile && (!profile.name || profile.name.trim().length < 2) && <ProfileCompletion profile={profile} onSaved={setProfile} />}
  </div>;
}
