import { Info } from "lucide-react";
import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/** KPI tile: label, headline value, optional sub-line and a definition tooltip. */
export function StatCard({
  label,
  value,
  sub,
  help,
  unavailable,
  className,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  help?: string;
  unavailable?: string;
  className?: string;
}) {
  return (
    <Card className={cn("gap-0", className)} size="sm">
      <CardContent>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          {label}
          {(help || unavailable) && (
            <Tooltip>
              <TooltipTrigger
                render={<button type="button" aria-label={`About ${label}`} className="text-muted-foreground/70" />}
              >
                <Info className="size-3" />
              </TooltipTrigger>
              <TooltipContent className="max-w-64">{unavailable ?? help}</TooltipContent>
            </Tooltip>
          )}
        </div>
        {unavailable ? (
          <p className="mt-1 text-sm text-muted-foreground">Not available</p>
        ) : (
          <p className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
        )}
        {sub && !unavailable && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
      </CardContent>
    </Card>
  );
}
