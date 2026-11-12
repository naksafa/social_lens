"use client";

import { LayoutGrid, Loader2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";

import { FindingsList } from "@/components/analytics/findings-list";
import { PostList } from "@/components/analytics/post-list";
import { PostsTable } from "@/components/analytics/posts-table";
import { HBarChart, MixChart } from "@/components/charts/charts";
import { EmptyState, ErrorState, LoadingGrid } from "@/components/project/states";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAnalytics } from "@/hooks/use-api";
import { ApiError, errorMessage } from "@/lib/api";
import { compact, num, pct, PLATFORM_LABEL, platformColor, titleCase } from "@/lib/format";
import { keys, projectsApi } from "@/services/projects";
import type { PostCard } from "@/types/api";

const PILLAR_ORDER = ["educational", "promotional", "social_proof", "entertainment", "brand", "community", "other"];
const RANKINGS = {
  top_by_performance_index: { label: "Performance index", metric: "performance_index" },
  top_by_exposure: { label: "Reach / views", metric: "exposure" },
  top_by_engagement: { label: "Engagement", metric: "engagement" },
  top_by_engagement_rate: { label: "Engagement rate", metric: "er" },
  top_by_saves: { label: "Saves", metric: "saves" },
  top_by_shares: { label: "Shares", metric: "shares" },
  top_by_clicks: { label: "Clicks", metric: "clicks" },
  top_videos_by_views: { label: "Video views", metric: "views" },
  top_videos_by_completion: { label: "Video completion", metric: "completion" },
} as const;
const BOTTOM = {
  bottom_by_performance_index: { label: "Performance index", metric: "performance_index" },
  bottom_by_engagement_rate: { label: "Engagement rate", metric: "er" },
} as const;

export default function ContentPage() {
  const { id } = useParams<{ id: string }>();
  const { mutate } = useSWRConfig();
  const { data, error, isLoading } = useAnalytics(id);
  const [platform, setPlatform] = useState<string | null>(null);
  const [ranking, setRanking] = useState<keyof typeof RANKINGS>("top_by_performance_index");
  const [bottom, setBottom] = useState<keyof typeof BOTTOM>("bottom_by_performance_index");
  const [classifying, setClassifying] = useState(false);

  if (isLoading) return <LoadingGrid />;
  if (error instanceof ApiError && error.status === 404)
    return (
      <EmptyState
        icon={LayoutGrid}
        title="No analysis yet"
        description="Content analysis appears once data is imported and analyzed."
        action={<Link href={`/projects/${id}/data`} className={buttonVariants()}>Go to data</Link>}
      />
    );
  if (error) return <ErrorState error={error} />;
  const platforms = data?.sections.platforms;
  if (!platforms) return null;
  const keysP = Object.keys(platforms);
  const current = platform && platforms[platform] ? platform : keysP[0];
  const s = platforms[current];
  const top = s.top_content;
  const findings = (data.sections.findings ?? []).filter(
    (f) => f.platform === current && ["pillar", "hook", "cta", "video"].includes(f.category),
  );
  const breakouts = s.anomalies.metrics.exposure?.over_performers ?? [];

  async function classify() {
    setClassifying(true);
    try {
      const res = await projectsApi.classify(id);
      toast.success(`${res.posts_updated} posts re-classified by AI`, { description: res.note });
      await mutate(keys.analytics(id));
    } catch (err) {
      toast.error("AI classification unavailable", { description: errorMessage(err) });
    } finally {
      setClassifying(false);
    }
  }

  const platformItems = Object.fromEntries(keysP.map((p) => [p, PLATFORM_LABEL[p]]));

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Content pillar mix</CardTitle>
              <CardDescription>
                Share of posts per pillar. Topics are classified from captions (keyword rules; optional AI re-classification
                for low-confidence posts).
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={classify} disabled={classifying}>
              {classifying ? <Loader2 className="animate-spin" /> : <Sparkles />} Refine with AI
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <MixChart
            order={PILLAR_ORDER}
            rows={keysP.map((p) => ({ label: PLATFORM_LABEL[p], mix: platforms[p].pillars.pillar_distribution }))}
          />
        </CardContent>
      </Card>

      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">Platform</span>
        <Select items={platformItems} value={current} onValueChange={(v) => v && setPlatform(v)}>
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {keysP.map((p) => (
              <SelectItem key={p} value={p}>
                {PLATFORM_LABEL[p]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Badge variant="outline">
          {s.pillars.classification.low_confidence_share !== null &&
            `${num(s.pillars.classification.low_confidence_share, 0)}% of posts low-confidence topic`}
        </Badge>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Pillar performance</CardTitle>
            <CardDescription>Median engagement rate by pillar ({PLATFORM_LABEL[current]})</CardDescription>
          </CardHeader>
          <CardContent>
            <HBarChart
              rows={s.pillars.pillars
                .filter((r) => typeof r.median_er === "number")
                .map((r) => ({ label: titleCase(r.group), value: r.median_er as number, low: r.low_sample, count: r.count }))}
              color={platformColor(current)}
              format={(v) => `${num(v, 2)}%`}
            />
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
              {s.pillars.pillars.map((r) => (
                <div key={r.group} className="rounded-md bg-muted/50 px-2 py-1.5">
                  <p className="font-medium">{titleCase(r.group)}</p>
                  <p className="text-muted-foreground">
                    {r.count} posts · save {pct(r.median_save_rate as number, 2)} · share {pct(r.median_share_rate as number, 2)}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Hooks & calls-to-action</CardTitle>
            <CardDescription>
              CTA usage: {pct(s.hooks_ctas.cta_usage_pct, 0)} of posts · detected from captions
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <HBarChart
              rows={s.hooks_ctas.hooks
                .filter((r) => typeof r.median_exposure === "number")
                .map((r) => ({ label: titleCase(r.group), value: r.median_exposure as number, low: r.low_sample, count: r.count }))}
              color={platformColor(current)}
              format={compact}
            />
            <p className="text-xs text-muted-foreground">Median {s.exposure_metric} by opening hook type.</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(s.hooks_ctas.cta_distribution).map(([k, v]) => (
                <Badge key={k} variant="secondary" className="font-normal">
                  {titleCase(k)} {num(v, 0)}%
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <CardTitle>Best-performing posts</CardTitle>
                <CardDescription>
                  Rate rankings only include posts with ≥ {compact(top.rate_ranking_min_exposure as number)} exposure.
                </CardDescription>
              </div>
              <Select items={Object.fromEntries(Object.entries(RANKINGS).map(([k, v]) => [k, v.label]))} value={ranking} onValueChange={(v) => v && setRanking(v as keyof typeof RANKINGS)}>
                <SelectTrigger size="sm" className="w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(RANKINGS).map(([k, v]) => (
                    <SelectItem key={k} value={k}>
                      {v.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent>
            <PostList posts={(top[ranking] as PostCard[]) ?? []} metric={RANKINGS[ranking].metric as keyof PostCard} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <CardTitle>Weakest posts</CardTitle>
                <CardDescription>Lowest scores among eligible posts.</CardDescription>
              </div>
              <Select items={Object.fromEntries(Object.entries(BOTTOM).map(([k, v]) => [k, v.label]))} value={bottom} onValueChange={(v) => v && setBottom(v as keyof typeof BOTTOM)}>
                <SelectTrigger size="sm" className="w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(BOTTOM).map(([k, v]) => (
                    <SelectItem key={k} value={k}>
                      {v.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent>
            <PostList posts={(top[bottom] as PostCard[]) ?? []} metric={BOTTOM[bottom].metric as keyof PostCard} />
          </CardContent>
        </Card>
      </div>

      {breakouts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Breakout posts</CardTitle>
            <CardDescription>{s.anomalies.method}</CardDescription>
          </CardHeader>
          <CardContent>
            <PostList posts={breakouts} metric="exposure" />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Content findings</CardTitle>
          <CardDescription>Pillar, hook, CTA and video tests for {PLATFORM_LABEL[current]}.</CardDescription>
        </CardHeader>
        <CardContent>
          <FindingsList findings={findings} />
        </CardContent>
      </Card>

      <Tabs defaultValue="posts">
        <TabsList>
          <TabsTrigger value="posts">All posts</TabsTrigger>
        </TabsList>
        <TabsContent value="posts" className="mt-3">
          <PostsTable projectId={id} platforms={keysP} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
