import type { TokenResponse } from "./types";

/** Access token lives in memory only (never storage) per the security architecture. */
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export class ApiError extends Error {
  readonly status: number;
  readonly title: string;
  readonly fieldErrors: { path: string; message: string }[];

  constructor(status: number, title: string, detail?: string,
              fieldErrors?: { path: string; message: string }[]) {
    super(detail || title);
    this.status = status;
    this.title = title;
    this.fieldErrors = fieldErrors ?? [];
  }
}

type Json = Record<string, unknown> | unknown[] | null;

async function parseProblem(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as {
      title?: string;
      detail?: string;
      errors?: { path: string; message: string }[];
    };
    return new ApiError(res.status, body.title ?? res.statusText, body.detail, body.errors);
  } catch {
    return new ApiError(res.status, res.statusText);
  }
}

/** One in-flight refresh shared by all 401-retrying requests. */
let refreshPromise: Promise<boolean> | null = null;

export async function tryRefresh(): Promise<boolean> {
  refreshPromise ??= (async () => {
    try {
      const res = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) return false;
      const body = (await res.json()) as TokenResponse;
      setAccessToken(body.accessToken);
      return true;
    } catch {
      return false;
    } finally {
      // allow the next refresh attempt after this one settles
      setTimeout(() => (refreshPromise = null), 0);
    }
  })();
  return refreshPromise;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: Json;
  params?: Record<string, string | number | boolean | undefined>;
  /** internal: prevents infinite refresh loops */
  _retried?: boolean;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(path, window.location.origin);
  for (const [key, value] of Object.entries(options.params ?? {})) {
    if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
  }

  const res = await fetch(url, {
    method: options.method ?? "GET",
    credentials: "include",
    headers: {
      ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (res.status === 401 && !options._retried && !path.startsWith("/api/v1/auth/login")) {
    if (await tryRefresh()) {
      return api<T>(path, { ...options, _retried: true });
    }
    window.dispatchEvent(new CustomEvent("saig:session-expired"));
    throw await parseProblem(res);
  }

  if (!res.ok) throw await parseProblem(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
