import NextAuth from "next-auth";
import { authConfig, isEmailAllowed } from "@/auth.config";

export { isEmailAllowed };

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  events: {
    // Runs in the Node.js auth route (never in edge middleware), so it is
    // safe to touch the database here.
    async signIn({ user }) {
      if (process.env.DATABASE_URL && user.email) {
        try {
          const { getStore } = await import("@/server/store");
          await getStore().upsertUser(user.email, user.name ?? null);
        } catch {
          // Never block sign-in on a bookkeeping failure.
        }
      }
    },
  },
});
