import { NextResponse } from "next/server";
import { backendBaseUrl, clearAuthCookies, getAccessToken, refreshAccessToken } from "@/lib/server-api";

export async function GET() {
  const accessToken = await getAccessToken();
  if (!accessToken) return NextResponse.json(null, { status: 401 });
  let response = await fetch(`${backendBaseUrl()}/auth/me`, {
    headers: { authorization: `Bearer ${accessToken}` },
    cache: "no-store"
  });
  if (response.status === 401) {
    const refreshedToken = await refreshAccessToken();
    if (refreshedToken) {
      response = await fetch(`${backendBaseUrl()}/auth/me`, {
        headers: { authorization: `Bearer ${refreshedToken}` },
        cache: "no-store"
      });
    }
  }
  if (!response.ok) {
    await clearAuthCookies();
    return NextResponse.json(null, { status: 401 });
  }
  return NextResponse.json(await response.json());
}
