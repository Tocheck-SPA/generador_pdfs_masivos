import { NextResponse } from "next/server";
import { auth } from "@/auth";

export interface SessionInfo {
  email: string | null;
  name: string | null;
}

/**
 * Return the authenticated user's info, or a 401 JSON response to return
 * directly from the route handler.
 */
export async function requireSession(): Promise<
  { ok: true; session: SessionInfo } | { ok: false; response: NextResponse }
> {
  const session = await auth();
  if (!session?.user?.email) {
    return {
      ok: false,
      response: NextResponse.json({ error: "No autenticado" }, { status: 401 }),
    };
  }
  return {
    ok: true,
    session: { email: session.user.email, name: session.user.name ?? null },
  };
}

export function jsonError(message: string, status = 400): NextResponse {
  return NextResponse.json({ error: message }, { status });
}

/** Extract a readable message from a Zod error without leaking internals. */
export function zodMessage(error: unknown): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "issues" in error &&
    Array.isArray((error as { issues: unknown[] }).issues)
  ) {
    const issues = (error as { issues: { message: string }[] }).issues;
    return issues.map((i) => i.message).join("; ") || "Datos inválidos";
  }
  return "Datos inválidos";
}
