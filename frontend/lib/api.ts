import { getApiBaseUrl } from "@/lib/config";
import type { ApiErrorBody } from "@/types/api";

/** Error thrown for any non-2xx response, carrying the backend's structured error. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.details = body.details;
  }
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return typeof value === "object" && value !== null && "code" in value && "message" in value;
}

export function apiUrl(path: string): string {
  return `${getApiBaseUrl()}${path}`;
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(0, {
      code: "network_error",
      message: "Cannot reach the SocialLens API. Is the backend running?",
      details: {},
    });
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      isApiErrorBody(body)
        ? { ...body, details: body.details ?? {} }
        : { code: "http_error", message: response.statusText || "Request failed", details: {} },
    );
  }
  return response;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await request(path, init);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function apiBlob(path: string, init?: RequestInit): Promise<Blob> {
  return (await request(path, init)).blob();
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, {
      method: "POST",
      body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body),
    }),
  put: <T>(path: string, body: unknown) => apiFetch<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  delete: (path: string) => apiFetch<void>(path, { method: "DELETE" }),
};

/** SWR fetcher: keys are API paths. */
export const fetcher = <T>(path: string) => apiFetch<T>(path);

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const missing = err.details?.missing;
    return Array.isArray(missing) ? `${err.message} (${missing.join(", ")})` : err.message;
  }
  return err instanceof Error ? err.message : "Something went wrong.";
}
