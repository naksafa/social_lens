/**
 * Backend base URL.
 * - Browser: NEXT_PUBLIC_API_URL (inlined at build time), e.g. http://localhost:8000
 * - Server (SSR inside Docker): API_INTERNAL_URL, e.g. http://backend:8000
 */
export function getApiBaseUrl(): string {
  const publicUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  if (typeof window === "undefined") {
    return process.env.API_INTERNAL_URL ?? publicUrl;
  }
  return publicUrl;
}
