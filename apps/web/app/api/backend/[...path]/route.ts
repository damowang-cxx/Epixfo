import { proxyToBackend } from "@/lib/server-api";

type Context = { params: Promise<{ path: string[] }> };

export async function GET(request: Request, context: Context) {
  const { path } = await context.params;
  return proxyToBackend(request, path);
}

export async function POST(request: Request, context: Context) {
  const { path } = await context.params;
  return proxyToBackend(request, path);
}

export async function PATCH(request: Request, context: Context) {
  const { path } = await context.params;
  return proxyToBackend(request, path);
}

export async function PUT(request: Request, context: Context) {
  const { path } = await context.params;
  return proxyToBackend(request, path);
}

export async function DELETE(request: Request, context: Context) {
  const { path } = await context.params;
  return proxyToBackend(request, path);
}
