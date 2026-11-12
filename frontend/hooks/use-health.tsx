"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { ApiError } from "@/lib/api";
import { getHealth } from "@/services/system";
import type { HealthResponse } from "@/types/api";

type HealthState =
  | { state: "loading" }
  | { state: "ready"; data: HealthResponse }
  | { state: "error"; error: ApiError };

interface HealthContextValue {
  health: HealthState;
  refresh: () => void;
}

const HealthContext = createContext<HealthContextValue | null>(null);

/** Polls the backend /health endpoint once for the whole app shell. */
export function HealthProvider({ children, pollMs = 30_000 }: { children: ReactNode; pollMs?: number }) {
  const [health, setHealth] = useState<HealthState>({ state: "loading" });

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      setHealth({ state: "ready", data: await getHealth(signal) });
    } catch (err) {
      if (signal?.aborted) return;
      setHealth({
        state: "error",
        error:
          err instanceof ApiError
            ? err
            : new ApiError(0, { code: "unknown", message: String(err), details: {} }),
      });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    // Fetching in an effect is intentional: this is a live polling status probe.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load(controller.signal);
    const id = setInterval(() => load(controller.signal), pollMs);
    return () => {
      controller.abort();
      clearInterval(id);
    };
  }, [load, pollMs]);

  return (
    <HealthContext.Provider value={{ health, refresh: () => void load() }}>
      {children}
    </HealthContext.Provider>
  );
}

export function useHealth(): HealthContextValue {
  const ctx = useContext(HealthContext);
  if (!ctx) throw new Error("useHealth must be used inside <HealthProvider>");
  return ctx;
}
