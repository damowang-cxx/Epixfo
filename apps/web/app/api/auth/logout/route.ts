import { NextResponse } from "next/server";
import { backendBaseUrl, clearAuthCookies, getAccessToken, getRefreshToken } from "@/lib/server-api";

export async function POST() {
  const refreshToken = await getRefreshToken();
  const accessToken = await getAccessToken();
  if (refreshToken && accessToken) {
    await fetch(`${backendBaseUrl()}/auth/logout`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${accessToken}`
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store"
    }).catch(() => undefined);
  }
  await clearAuthCookies();
  return NextResponse.json({ ok: true });
}
