"use client";

import { Bot, Database, Server } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useHealth } from "@/hooks/use-health";

function StatusCard({
  icon: Icon,
  label,
  value,
  hint,
  ok,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  hint: string;
  ok: boolean | null;
}) {
  return (
    <Card>
      <CardContent className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
          <Icon className="size-4 text-muted-foreground" />
        </span>
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p
            className={
              ok === false ? "font-medium text-destructive" : "font-medium text-foreground"
            }
          >
            {value}
          </p>
          <p className="mt-0.5 truncate text-xs text-muted-foreground" title={hint}>
            {hint}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

export function SystemOverview() {
  const { health } = useHealth();

  if (health.state === "loading") {
    return (
      <div className="grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-[92px] rounded-xl" />
        ))}
      </div>
    );
  }

  if (health.state === "error") {
    return (
      <div className="grid gap-4 sm:grid-cols-3">
        <StatusCard
          icon={Server}
          label="API"
          value="Unreachable"
          hint={health.error.message}
          ok={false}
        />
      </div>
    );
  }

  const { data } = health;
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <StatusCard
        icon={Server}
        label="API"
        value={`Online · v${data.version}`}
        hint={`Environment: ${data.environment}`}
        ok
      />
      <StatusCard
        icon={Database}
        label="Database"
        value={data.database.status === "ok" ? "Connected" : "Unavailable"}
        hint={data.database.detail ?? "SQL database"}
        ok={data.database.status === "ok"}
      />
      <StatusCard
        icon={Bot}
        label="AI provider"
        value={data.ai.status === "ok" ? (data.ai.detail ?? "Configured") : "Not configured"}
        hint={
          data.ai.status === "ok"
            ? "AI audit & strategy enabled"
            : "Analytics run without AI; add an API key to enable audits."
        }
        ok={null}
      />
    </div>
  );
}
