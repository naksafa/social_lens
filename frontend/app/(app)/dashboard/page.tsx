"use client";

import { ArrowRight, FileText, FolderOpen, Plus, TrendingDown, TrendingUp } from "lucide-react";
import Link from "next/link";

import { DemoDialog } from "@/components/project/demo-dialog";
import { PlatformBadge } from "@/components/project/badges";
import { EmptyState, ErrorState } from "@/components/project/states";
import { PageHeader } from "@/components/layout/page-header";
import { SystemOverview } from "@/components/system/system-overview";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useProjects } from "@/hooks/use-api";
import { compact, dateTime, pct, PLATFORM_LABEL, titleCase } from "@/lib/format";
import type { ProjectListItem } from "@/types/api";

function ProjectCard({ p }: { p: ProjectListItem }) {
  const headline = p.latest_run?.headline;
  const platforms = headline?.platforms ?? {};
  return (
    <Link href={`/projects/${p.id}`} className="group">
      <Card className="h-full transition-shadow group-hover:shadow-md">
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <CardTitle className="truncate">{p.business_profile?.business_name ?? p.name}</CardTitle>
              <p className="truncate text-xs text-muted-foreground">
                {p.business_profile?.industry ?? "—"}
                {p.business_profile?.city_market ? ` · ${p.business_profile.city_market}` : ""}
              </p>
            </div>
            <div className="flex shrink-0 gap-1">
              {p.is_demo && <Badge variant="outline">Demo</Badge>}
              <Badge variant="secondary">{titleCase(p.status)}</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-1">
            {p.platforms.map((pl) => (
              <PlatformBadge key={pl} platform={pl} />
            ))}
          </div>
          {p.latest_run ? (
            <div className="grid grid-cols-2 gap-2 text-sm">
              {Object.entries(platforms)
                .slice(0, 4)
                .map(([pl, h]) => (
                  <div key={pl} className="rounded-lg bg-muted/50 px-2.5 py-1.5">
                    <p className="text-xs text-muted-foreground">{PLATFORM_LABEL[pl] ?? pl}</p>
                    <p className="flex items-center gap-1 font-medium tabular-nums">
                      {pct(h.median_engagement_rate, 2)} ER
                      {h.exposure_trend === "growth" && <TrendingUp className="size-3.5 text-emerald-600" />}
                      {h.exposure_trend === "decline" && <TrendingDown className="size-3.5 text-red-600" />}
                    </p>
                  </div>
                ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              {p.files.count ? `${p.files.count} file(s) uploaded - not analyzed yet` : "No data uploaded yet"}
            </p>
          )}
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {compact(p.post_count)} posts
              {p.latest_run && ` · analysis v${p.latest_run.analysis_version}`}
            </span>
            <span>{p.latest_run?.finished_at ? dateTime(p.latest_run.finished_at) : dateTime(p.updated_at)}</span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

export default function DashboardPage() {
  const { data: projects, error, isLoading } = useProjects();
  const withReports = (projects ?? []).filter((p) => p.has_audit);

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Dashboard"
        description="Your social media audits, analyses and reports."
        actions={
          <>
            <DemoDialog />
            <Link href="/projects/new" className={buttonVariants()}>
              <Plus /> New project
            </Link>
          </>
        }
      />

      <SystemOverview />

      <section className="mt-10">
        <h2 className="mb-3 text-sm font-medium text-muted-foreground">Projects</h2>
        {error ? (
          <ErrorState error={error} />
        ) : isLoading ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-52 rounded-xl" />
            ))}
          </div>
        ) : !projects?.length ? (
          <EmptyState
            icon={FolderOpen}
            title="No projects yet"
            description="Create a project and upload your platform exports, or generate a fully analyzed demo project in one click."
            action={
              <div className="flex gap-2">
                <DemoDialog />
                <Link href="/projects/new" className={buttonVariants()}>
                  <Plus /> New project
                </Link>
              </div>
            }
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {projects.map((p) => (
              <ProjectCard key={p.id} p={p} />
            ))}
          </div>
        )}
      </section>

      {withReports.length > 0 && (
        <section className="mt-10">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Recent reports</h2>
          <Card>
            <CardContent className="divide-y p-0">
              {withReports.slice(0, 5).map((p) => (
                <Link
                  key={p.id}
                  href={`/projects/${p.id}/report`}
                  className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-muted/50"
                >
                  <FileText className="size-4 text-muted-foreground" />
                  <span className="font-medium">{p.business_profile?.business_name ?? p.name}</span>
                  <span className="text-muted-foreground">
                    {p.has_strategy ? "Audit + strategy" : "Audit"} · {dateTime(p.updated_at)}
                  </span>
                  <ArrowRight className="ml-auto size-4 text-muted-foreground" />
                </Link>
              ))}
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}
