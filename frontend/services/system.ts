import { apiFetch } from "@/lib/api";
import type { HealthResponse } from "@/types/api";

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health", { signal, cache: "no-store" });
}
