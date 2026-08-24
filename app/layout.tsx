import type { Metadata } from 'next';
import './globals.css';
import './phase3b.css';
import './phase3c.css';
import './phase3a5.css';

import { AuthSessionProvider } from './components/AuthSessionProvider';

export const metadata: Metadata = { title: 'HelixMind — Scientific Intelligence. Reasoned.', description: 'An AI-native scientific intelligence workstation for CRISPR research.', icons: { icon: '/helixmindcoverimage.jpg' } };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body><AuthSessionProvider>{children}</AuthSessionProvider></body></html>; }
