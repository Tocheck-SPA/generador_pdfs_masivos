import { NextResponse } from "next/server";
import { getSource } from "@/server/source";
import { companyIdQuerySchema } from "@/validation/schemas";
import { jsonError, requireSession, zodMessage } from "@/server/api-helpers";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const gate = await requireSession();
  if (!gate.ok) return gate.response;

  const { searchParams } = new URL(request.url);
  const parsed = companyIdQuerySchema.safeParse({
    companyId: searchParams.get("companyId") ?? "",
  });
  if (!parsed.success) return jsonError(zodMessage(parsed.error));

  try {
    const forms = await getSource().listForms(parsed.data.companyId);
    return NextResponse.json(forms);
  } catch {
    return jsonError("No se pudieron cargar los formularios", 500);
  }
}
