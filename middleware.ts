import { withAuth } from 'next-auth/middleware';
import { decodeAuthToken } from '@/lib/auth';

export default withAuth(
  {
    callbacks: { authorized: ({ token, req }) => (req.nextUrl.pathname.startsWith('/admin') ? token?.role === 'ADMIN' : Boolean(token?.sub)) },
    jwt: { decode: decodeAuthToken },
    pages: { signIn: '/login' },
    secret: process.env.NEXTAUTH_SECRET,
  },
);

export const config = {
  matcher: ['/dashboard/:path*', '/investigations/:path*', '/literature/:path*', '/knowledge/:path*', '/hypotheses/:path*', '/settings/:path*', '/admin/:path*'],
};
