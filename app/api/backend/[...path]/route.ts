import { getToken } from 'next-auth/jwt';
import { NextRequest, NextResponse } from 'next/server';

import { decodeAuthToken } from '@/lib/auth';

export const dynamic = 'force-dynamic';

async function forward(request: NextRequest, { params }: { params: { path: string[] } }) {
  const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET, decode: decodeAuthToken });
  if (!token?.sub) return NextResponse.json({ detail: 'Authentication required.' }, { status: 401 });

  const rawToken = await getToken({ req: request, raw: true, secret: process.env.NEXTAUTH_SECRET });
  const backendUrl = process.env.HELIXMIND_BACKEND_URL;
  if (!backendUrl || !rawToken) return NextResponse.json({ detail: 'Backend authentication is not configured.' }, { status: 503 });

  const target = `${backendUrl.replace(/\/$/, '')}/${params.path.join('/')}${request.nextUrl.search}`;
  const body = ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer();
  const response = await fetch(target, {
    method: request.method,
    headers: {
      Authorization: `Bearer ${rawToken}`,
      ...(request.headers.get('content-type') ? { 'Content-Type': request.headers.get('content-type') as string } : {}),
    },
    body,
    cache: 'no-store',
  });
  const responseBody = await response.arrayBuffer();
  return new NextResponse(responseBody, {
    status: response.status,
    headers: { 'Content-Type': response.headers.get('content-type') ?? 'application/json' },
  });
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
