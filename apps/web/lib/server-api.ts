import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const ACCESS_COOKIE = "epixfo_access_token";
const REFRESH_COOKIE = "epixfo_refresh_token";

export function backendBaseUrl() {
  return process.env.BACKEND_API_URL || "http://127.0.0.1:8000/api/v1";
}

function authCookieSecure() {
  return process.env.AUTH_COOKIE_SECURE === "true";
}

export async function setAuthCookies(accessToken: string, refreshToken: string) {
  const cookieStore = await cookies();
  const secure = authCookieSecure();
  cookieStore.set(ACCESS_COOKIE, accessToken, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: 60 * 30
  });
  cookieStore.set(REFRESH_COOKIE, refreshToken, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: 60 * 60 * 24 * 14
  });
}

export async function clearAuthCookies() {
  const cookieStore = await cookies();
  cookieStore.delete(ACCESS_COOKIE);
  cookieStore.delete(REFRESH_COOKIE);
}

export async function getAccessToken() {
  return (await cookies()).get(ACCESS_COOKIE)?.value;
}

export async function getRefreshToken() {
  return (await cookies()).get(REFRESH_COOKIE)?.value;
}

export async function refreshAccessToken() {
  const refreshToken = await getRefreshToken();
  if (!refreshToken) return null;
  const response = await fetch(`${backendBaseUrl()}/auth/refresh`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: "no-store"
  });
  if (!response.ok) {
    await clearAuthCookies();
    return null;
  }
  const data = (await response.json()) as { access_token: string; refresh_token: string };
  await setAuthCookies(data.access_token, data.refresh_token);
  return data.access_token;
}

export async function proxyToBackend(request: Request, path: string[]) {
  const url = new URL(request.url);
  const target = `${backendBaseUrl()}/${path.join("/")}${url.search}`;
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("cookie");
  const accessToken = await getAccessToken();
  if (accessToken) headers.set("authorization", `Bearer ${accessToken}`);

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store"
  };
  if (!["GET", "HEAD"].includes(request.method)) {
    init.body = await request.text();
  }

  let response = await fetch(target, init);
  if (response.status === 401) {
    const newAccessToken = await refreshAccessToken();
    if (newAccessToken) {
      headers.set("authorization", `Bearer ${newAccessToken}`);
      response = await fetch(target, { ...init, headers });
    }
  }

  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") || "application/json"
    }
  });
}
