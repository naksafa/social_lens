"use client";

import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useHealth } from "@/hooks/use-health";
import { cn } from "@/lib/utils";

/** Compact live indicator of backend / database / AI provider status. */
export function BackendStatus() {
  const { health } = useHealth();

  let tone: "ok" | "warn" | "down" | "loading" = "loading";
  let label = "Connecting…";
  let detail = "Checking the SocialLens API.";

  if (health.state === "error") {
    tone = "down";
    label = "API offline";
    detail = health.error.message;
  } else if (health.state === "ready") {
    const { data } = health;
    if (data.database.status !== "ok") {
      tone = "down";
      label = "Database unavailable";
      detail = "The API is up but cannot reach PostgreSQL.";
    } else if (data.ai.status !== "ok") {
      tone = "warn";
      label = "Analytics only";
      detail = data.ai.detail ?? "No AI provider configured.";
    } else {
      tone = "ok";
      label = `AI: ${data.ai.detail}`;
      detail = `API v${data.version} · ${data.environment}`;
    }
  }

  return (
    <Tooltip>
      <TooltipTrigger render={<Badge variant="outline" className="gap-1.5 font-normal" />}>
        <span
          aria-hidden
          className={cn(
            "size-2 rounded-full",
            tone === "ok" && "bg-emerald-500",
            tone === "warn" && "bg-amber-500",
            tone === "down" && "bg-red-500",
            tone === "loading" && "animate-pulse bg-muted-foreground",
          )}
        />
        {label}
      </TooltipTrigger>
      <TooltipContent>{detail}</TooltipContent>
    </Tooltip>
  );
}
