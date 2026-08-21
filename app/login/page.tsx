'use client';

import { signIn } from 'next-auth/react';
import Link from 'next/link';

import { Brand } from '../components/Brand';

export default function LoginPage() {
  return <main className="auth-page"><div className="auth-card"><Brand /><p className="eyebrow">RESEARCHER ACCESS</p><h1>Continue your scientific work.</h1><p className="auth-copy">Sign in to create investigations, follow evidence chains, and keep your research history private to your account.</p><button className="google-button" onClick={() => signIn('google', { callbackUrl: '/dashboard' })}><span>G</span> Continue with Google <b>↗</b></button><p className="privacy-note">Authentication is handled through Google OAuth. HelixMind stores your account identity and research artifacts; provider credentials are never exposed to the browser.</p><Link href="/" className="back-link">← Back to HelixMind</Link></div></main>;
}
