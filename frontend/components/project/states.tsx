import { AlertCircle, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
        <span className="mb-1 flex size-10 items-center justify-center rounded-full bg-muted">
          <Icon className="size-5 text-muted-foreground" />
        </span>
        <p className="font-medium">{title}</p>
        {description && <p className="max-w-md text-sm text-muted-foreground">{description}</p>}
        {action && <div className="mt-3">{action}</div>}
      </CardContent>
    </Card>
  );
}

export function ErrorState({ error, action }: { error: unknown; action?: ReactNode }) {
  return (
    <Card className="border-destructive/30">
      <CardContent className="flex items-start gap-3">
        <AlertCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">Something went wrong</p>
          <p className="text-sm text-muted-foreground">{errorMessage(error)}</p>
        </div>
        {action}
      </CardContent>
    </Card>
  );
}

export function LoadingGrid({ rows = 2 }: { rows?: number }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-64 rounded-xl" />
      ))}
    </div>
  );
}
