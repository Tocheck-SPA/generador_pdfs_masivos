import { NextResponse } from "next/server";
import { getSource } from "@/server/source";
import { jsonError, requireSession } from "@/server/api-helpers";

export const runtime = "nodejs";

export async function GET() {
  const gate = await requireSession();
  if (!gate.ok) return gate.response;
  try {
    const companies = await getSource().listCompanies();
    return NextResponse.json(companies);
  } catch {
    return jsonError("No se pudieron cargar las empresas", 500);
  }
}
