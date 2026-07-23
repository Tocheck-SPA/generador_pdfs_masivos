import NextAuth from "next-auth";
import { authConfig } from "@/auth.config";

const { auth } = NextAuth(authConfig);

export default auth((req) => {
  const isAuthed = Boolean(req.auth?.user);
  const { pathname } = req.nextUrl;

  const isPublic =
    pathname.startsWith("/login") || pathname.startsWith("/api/auth");

  if (!isAuthed && !isPublic) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("callbackUrl", pathname);
    return Response.redirect(url);
  }
  return undefined;
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
