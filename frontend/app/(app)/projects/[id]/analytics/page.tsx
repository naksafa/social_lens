"use client";

import { BarChart3, Loader2, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { CrossPlatformPanel } from "@/components/analytics/cross-platform-panel";
import { PlatformPanel } from "@/components/analytics/platform-panel";
import { EmptyState, ErrorState, LoadingGrid } from "@/components/project/states";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAnalytics } from "@/hooks/use-api";
import { ApiError, errorMessage } from "@/lib/api";
import { dateTime, PLATFORM_LABEL, platformColor, titleCase } from "@/lib/format";
import { keys, projectsApi } from "@/services/projects";

export default function AnalyticsPage() {
  const { id } = useParams<{ id: string }>();
  const { mutate } = useSWRConfig();
  const { data, error, isLoading } = useAnalytics(id);
  const [running, setRunning] = useState(false);

  async function rerun() {
    setRunning(true);
    try {
      const run = await projectsApi.analyze(id);
      await Promise.all([mutate(keys.analytics(id)), mutate(keys.insights(id)), mutate(keys.runs(id)), mutate(keys.projects)]);
      toast.success(`Analysis v${run.analysis_version} complete`, { description: "Previous versions are kept." });
    } catch (err) {
      toast.error("Analysis failed", { description: errorMessage(err) });
    } finally {
      setRunning(false);
    }
  }

  if (isLoading) return <LoadingGrid />;
  if (error instanceof ApiError && error.status === 404)
    return (
      <EmptyState
        icon={BarChart3}
        title="No analysis yet"
        description="Upload and import data, then run the analysis."
        action={
          <Link href={`/projects/${id}/data`} className={buttonVariants()}>
            Go to data
          </Link>
        }
      />
    );
  if (error) return <ErrorState error={error} />;
  if (!data?.sections.platforms || !data.sections.cross_platform) return null;

  const { run, sections } = data;
  const platformSections = data.sections.platforms;
  const cross = data.sections.cross_platform;
  const platforms = Object.keys(platformSections);
  const findings = sections.findings ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Badge variant="secondary">Analysis v{run.analysis_version}</Badge>
          <span>
            {sections.overview?.period_start} → {sections.overview?.period_end} · {sections.overview?.total_posts} posts ·
            computed {dateTime(run.finished_at)}
          </span>
          {run.parameters.objectives && run.parameters.objectives.length > 0 && (
            <span>· weights for {run.parameters.objectives.map(titleCase).join(", ")}</span>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={rerun} disabled={running}>
          {running ? <Loader2 className="animate-spin" /> : <RefreshCw />} Re-run analysis
        </Button>
      </div>

      <Tabs defaultValue={platforms[0]}>
        <TabsList className="h-auto flex-wrap">
          {platforms.map((p) => (
            <TabsTrigger key={p} value={p} className="gap-1.5">
              <span aria-hidden className="size-2 rounded-full" style={{ background: platformColor(p) }} />
              {PLATFORM_LABEL[p]}
            </TabsTrigger>
          ))}
          {platforms.length > 1 && <TabsTrigger value="cross">Cross-platform</TabsTrigger>}
        </TabsList>
        {platforms.map((p) => (
          <TabsContent key={p} value={p} className="mt-4">
            <PlatformPanel platform={p} s={platformSections[p]} findings={findings} />
          </TabsContent>
        ))}
        {platforms.length > 1 && (
          <TabsContent value="cross" className="mt-4">
            <CrossPlatformPanel cross={cross} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
