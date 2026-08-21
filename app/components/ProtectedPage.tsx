import { ProtectedShell } from './ProtectedShell';

export function ProtectedPage({ title, eyebrow, children, admin = false }: { title: string; eyebrow: string; children: React.ReactNode; admin?: boolean }) {
  return <ProtectedShell admin={admin}><div className="page-wrap"><p className="eyebrow">{eyebrow}</p><h1>{title}</h1>{children}</div></ProtectedShell>;
}
