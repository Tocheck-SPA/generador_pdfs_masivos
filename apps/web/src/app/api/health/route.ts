import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function GET() {
  return NextResponse.json({
    status: "ok",
    database: process.env.DATABASE_URL ? "postgres" : "memory",
    timestamp: new Date().toISOString(),
  });
}
