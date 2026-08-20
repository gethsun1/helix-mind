import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = { title: 'HelixMind — Scientific Intelligence. Reasoned.', description: 'An AI-native scientific intelligence workstation for CRISPR research.', icons: { icon: '/helixmindcoverimage.jpg' } };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
