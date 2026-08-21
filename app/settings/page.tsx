import { ProtectedPage } from '../components/ProtectedPage';

export default function SettingsPage() { return <ProtectedPage eyebrow="WORKSPACE / SETTINGS" title="Researcher profile."><div className="panel"><p>Your authenticated profile is stored in HelixMind PostgreSQL. Profile editing will be added after the core investigation vertical slice.</p></div></ProtectedPage>; }
