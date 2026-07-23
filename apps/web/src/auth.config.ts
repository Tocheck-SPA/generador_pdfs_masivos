import type { NextAuthConfig } from "next-auth";
import Google from "next-auth/providers/google";
import Credentials from "next-auth/providers/credentials";

function csv(name: string): string[] {
  return (process.env[name] ?? "")
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
}

/** Authorize by allow-list. If BOTH lists are empty, allow all (dev). */
export function isEmailAllowed(email: string | null | undefined): boolean {
  if (!email) return false;
  const normalized = email.trim().toLowerCase();
  const domains = csv("AUTH_ALLOWED_DOMAINS");
  const emails = csv("AUTH_ALLOWED_EMAILS");
  if (domains.length === 0 && emails.length === 0) return true;
  if (emails.includes(normalized)) return true;
  const domain = normalized.split("@")[1] ?? "";
  return domains.includes(domain);
}

const hasGoogle = Boolean(
  process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET
);
const devMode = process.env.AUTH_DEV_MODE === "true" || !hasGoogle;

const providers: NextAuthConfig["providers"] = [];

if (hasGoogle) {
  providers.push(
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    })
  );
}

if (devMode) {
  providers.push(
    Credentials({
      id: "dev-credentials",
      name: "Modo desarrollo",
      credentials: {
        email: { label: "Correo", type: "email" },
      },
      authorize(credentials) {
        const email =
          typeof credentials?.email === "string"
            ? credentials.email.trim().toLowerCase()
            : "";
        if (!email || !isEmailAllowed(email)) return null;
        return { id: email, email, name: email.split("@")[0] };
      },
    })
  );
}

/** Edge-safe config (no database access) shared with middleware. */
export const authConfig: NextAuthConfig = {
  providers,
  session: { strategy: "jwt" },
  pages: { signIn: "/login" },
  secret: process.env.NEXTAUTH_SECRET ?? "dev-secret-change-me",
  trustHost: true,
  callbacks: {
    authorized({ auth }) {
      return Boolean(auth?.user);
    },
    signIn({ user }) {
      return isEmailAllowed(user.email);
    },
    jwt({ token, user }) {
      if (user?.email) token.email = user.email;
      return token;
    },
    session({ session, token }) {
      if (session.user && token.email) session.user.email = token.email;
      return session;
    },
  },
};
