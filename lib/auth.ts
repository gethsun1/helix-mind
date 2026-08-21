import { jwtVerify, SignJWT } from 'jose';
import type { JWT } from 'next-auth/jwt';

function secretKey() {
  const secret = process.env.NEXTAUTH_SECRET;
  if (!secret) throw new Error('NEXTAUTH_SECRET is not configured.');
  return new TextEncoder().encode(secret);
}

export async function encodeAuthToken({ token, maxAge = 30 * 24 * 60 * 60 }: { token?: JWT; maxAge?: number }) {
  return new SignJWT((token ?? {}) as Record<string, unknown>)
    .setProtectedHeader({ alg: 'HS256', typ: 'JWT' })
    .setIssuedAt()
    .setExpirationTime(Math.floor(Date.now() / 1000) + maxAge)
    .sign(secretKey());
}

export async function decodeAuthToken({ token }: { token?: string }) {
  if (!token) return null;
  try {
    const verified = await jwtVerify(token, secretKey(), { algorithms: ['HS256'] });
    return verified.payload as JWT;
  } catch {
    return null;
  }
}

export async function syncGoogleUser(input: {
  email?: string | null;
  name?: string | null;
  image?: string | null;
  providerAccountId?: string | null;
}) {
  const backendUrl = process.env.HELIXMIND_BACKEND_URL;
  const syncSecret = process.env.HELIXMIND_AUTH_SYNC_SECRET;
  if (!backendUrl || !syncSecret) throw new Error('HelixMind authentication backend is not configured.');
  if (!input.email) throw new Error('Google did not provide an email address.');

  const response = await fetch(`${backendUrl.replace(/\/$/, '')}/api/v1/auth/sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-HelixMind-Auth-Sync': syncSecret },
    body: JSON.stringify({
      email: input.email,
      name: input.name ?? null,
      image: input.image ?? null,
      provider_account_id: input.providerAccountId ?? null,
    }),
    cache: 'no-store',
  });
  if (!response.ok) throw new Error('HelixMind could not persist the authenticated user.');
  return response.json() as Promise<{ id: string; role: string; email: string; name: string | null; image: string | null }>;
}
