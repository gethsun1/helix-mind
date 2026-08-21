import NextAuth, { type NextAuthOptions } from 'next-auth';
import GoogleProvider from 'next-auth/providers/google';

import { decodeAuthToken, encodeAuthToken, syncGoogleUser } from '@/lib/auth';

const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID ?? '',
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? '',
    }),
  ],
  secret: process.env.NEXTAUTH_SECRET,
  session: { strategy: 'jwt', maxAge: 30 * 24 * 60 * 60 },
  jwt: { encode: encodeAuthToken, decode: decodeAuthToken },
  callbacks: {
    async jwt({ token, user, account }) {
      if (user && account?.provider === 'google') {
        const persisted = await syncGoogleUser({
          email: user.email,
          name: user.name,
          image: user.image,
          providerAccountId: account.providerAccountId,
        });
        token.sub = persisted.id;
        token.email = persisted.email;
        token.name = persisted.name;
        token.picture = persisted.image;
        token.role = persisted.role;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.sub ?? '';
        session.user.role = String(token.role ?? 'USER');
      }
      return session;
    },
  },
  pages: { signIn: '/login' },
};

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };
