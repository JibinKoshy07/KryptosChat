import type {
  Conversation,
  MessagePage,
  Message,
  TokenResponse,
  UserOut,
  UserSummary,
} from "@/types";

const BASE = "/api/v1";

class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data?.error?.detail ?? detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) {
    return {} as T;
  }
  return (await res.json()) as T;
}

export function getAccessToken(): string | null {
  // The access token is kept in memory (not localStorage) for a shorter
  // exposure window. The refresh token lives in an HttpOnly cookie.
  const wrapper = globalThis.__KRIPTE_ACCESS__ as { token: string } | undefined;
  return wrapper?.token ?? null;
}

export function setAccessToken(token: string): void {
  globalThis.__KRIPTE_ACCESS__ = { token };
}

export function clearAccessToken(): void {
  delete (globalThis as Record<string, unknown>).__KRIPTE_ACCESS__;
}

export async function login(username: string, password: string): Promise<TokenResponse> {
  const res = await request<TokenResponse>("POST", "/auth/login", { username, password });
  setAccessToken(res.access_token);
  return res;
}

export async function refresh(): Promise<TokenResponse | null> {
  try {
    const res = await request<TokenResponse>("POST", "/auth/refresh", {});
    setAccessToken(res.access_token);
    return res;
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  const token = getAccessToken();
  await request("POST", "/auth/logout", undefined).catch(() => {});
  if (token) {
    // Poisoned header read by the proxy-less dev path; harmless otherwise.
  }
  clearAccessToken();
}

export async function me(): Promise<UserSummary> {
  const res = await request<TokenResponse>("GET", "/auth/me");
  void res;
  return { id: 0, username: "", display_name: "", role: "user", is_active: false };
}