export class ApiError extends Error {
  status: number;
  detail?: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (!isFormData && !headers.has("content-type")) headers.set("content-type", "application/json");

  const response = await fetch(`/api/backend${path}`, {
    ...init,
    headers
  });

  if (response.status === 401) {
    window.location.href = "/login";
    throw new ApiError(401, "未登录或登录已过期");
  }
  if (!response.ok) {
    const text = await response.text();
    const parsed = parseErrorPayload(text);
    throw new ApiError(response.status, parsed.message || "请求失败", parsed.detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function parseErrorPayload(text: string): { message: string; detail?: unknown } {
  if (!text) return { message: "" };
  try {
    const data = JSON.parse(text) as { detail?: unknown };
    if (typeof data.detail === "string") return { message: data.detail, detail: data.detail };
    if (data.detail && typeof data.detail === "object") {
      const detail = data.detail as { message?: unknown; error_code?: unknown };
      return {
        message:
          (typeof detail.message === "string" && detail.message) ||
          (typeof detail.error_code === "string" && detail.error_code) ||
          text,
        detail: data.detail
      };
    }
  } catch {
    return { message: text };
  }
  return { message: text };
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body)
    }),
  postForm: <T>(path: string, body: FormData) =>
    request<T>(path, {
      method: "POST",
      body
    }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PUT",
      body: body === undefined ? undefined : JSON.stringify(body)
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PATCH",
      body: body === undefined ? undefined : JSON.stringify(body)
    }),
  delete: <T>(path: string) =>
    request<T>(path, {
      method: "DELETE"
    })
};
