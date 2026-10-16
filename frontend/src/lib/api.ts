// Thin fetch wrapper. All requests are same-origin (/api is proxied to Django), so the
// session cookie rides along automatically; writes echo the CSRF cookie in a header.

export type ApiErrorBody = {
  code: string;
  message: string;
  details: Record<string, unknown>;
  request_id: string | null;
};

export class ApiError extends Error {
  constructor(public status: number, public body: ApiErrorBody) {
    super(body.message);
  }

  /** First field-level validation message, if any — handy for form errors. */
  fieldMessage(): string | null {
    const fields = (this.body.details?.fields ?? {}) as Record<string, unknown>;
    for (const [field, msgs] of Object.entries(fields)) {
      const first = Array.isArray(msgs) ? msgs[0] : msgs;
      if (first) return `${field.replace(/_/g, " ")}: ${typeof first === "string" ? first : JSON.stringify(first)}`;
    }
    return null;
  }
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

async function ensureCsrf() {
  if (!csrfToken()) await fetch("/api/v1/auth/csrf/", { credentials: "same-origin" });
}

function withSlash(path: string) {
  const [p, q] = path.split("?");
  return (p.endsWith("/") ? p : `${p}/`) + (q ? `?${q}` : "");
}

export async function api<T = unknown>(
  path: string,
  init: { method?: string; body?: unknown } = {},
): Promise<T> {
  const method = init.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    await ensureCsrf();
    headers["X-CSRFToken"] = csrfToken();
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`/api/v1${withSlash(path)}`, {
    method,
    headers,
    credentials: "same-origin",
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(
      res.status,
      data?.error ?? { code: "network_error", message: "Something went wrong.", details: {}, request_id: null },
    );
  }
  return data as T;
}

export const post = <T = unknown>(path: string, body: unknown = {}) => api<T>(path, { method: "POST", body });
export const patch = <T = unknown>(path: string, body: unknown) => api<T>(path, { method: "PATCH", body });
export const del = (path: string) => api(path, { method: "DELETE" });
