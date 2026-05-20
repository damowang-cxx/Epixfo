import { NextResponse } from "next/server";
import { backendBaseUrl, setAuthCookies } from "@/lib/server-api";

export async function POST(request: Request) {
  const body = await request.text();
  const response = await fetch(`${backendBaseUrl()}/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
    cache: "no-store"
  });
  const text = await response.text();
  if (!response.ok) {
    return new NextResponse(text, { status: response.status });
  }
  const data = JSON.parse(text) as { access_token: string; refresh_token: string };
  await setAuthCookies(data.access_token, data.refresh_token);
  return NextResponse.json({ ok: true });
}
