import Link from 'next/link';

import { Brand } from './Brand';
import { SignOutButton } from './SignOutButton';

const links = [
  ['/dashboard', 'Dashboard'],
  ['/investigations', 'Investigations'],
  ['/literature', 'Literature'],
  ['/knowledge', 'Knowledge Graph'],
  ['/hypotheses', 'Hypothesis Lab'],
  ['/settings', 'Settings'],
];

export function ProtectedShell({ children, admin = false }: { children: React.ReactNode; admin?: boolean }) {
  return <div className="app-shell"><aside className="sidebar"><Brand /><div className="sidebar-label">RESEARCH WORKSPACE</div><nav>{links.map(([href, label]) => <Link href={href} key={href}>{label}</Link>)}{admin && <Link href="/admin" className="admin-link">System Diagnostics</Link>}</nav><div className="sidebar-foot"><span className="status-dot" /> HelixMind services isolated</div><SignOutButton /></aside><main className="workspace"><header className="workspace-header"><span className="mono">HELIXMIND / WORKSPACE</span><Link href="/" className="back-link">Public overview ↗</Link></header>{children}</main></div>;
}
