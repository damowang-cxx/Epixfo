import { NextResponse } from "next/server";
import { refreshAccessToken } from "@/lib/server-api";

export async function POST() {
  const token = await refreshAccessToken();
  if (!token) return NextResponse.json({ ok: false }, { status: 401 });
  return NextResponse.json({ ok: true });
}
