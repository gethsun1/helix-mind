import { ProtectedPage } from '../components/ProtectedPage';

export default function InvestigationsPage() { return <ProtectedPage eyebrow="RESEARCH / INVESTIGATIONS" title="Your investigations."><div className="panel"><p>Investigation history is available from the authenticated dashboard and will expand here as the research workspace grows.</p></div></ProtectedPage>; }
