"use client";

import { TrendingDown, TrendingUp } from "lucide-react";

import { FindingsList } from "@/components/analytics/findings-list";
import { ColumnChart, HBarChart, ScatterPlot, TrendChart } from "@/components/charts/charts";
import { StatCard } from "@/components/project/stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { compact, formatLabel, num, pct, platformColor, shortDate, signedPct, titleCase } from "@/lib/format";
import type { Finding, GroupRow, PlatformSection, TrendInfo } from "@/types/api";

function TrendBadge({ t }: { t?: TrendInfo }) {
  if (!t || t.label === "insufficient_data") return <Badge variant="outline">Not enough weeks</Badge>;
  const Icon = t.label === "growth" ? TrendingUp : t.label === "decline" ? TrendingDown : null;
  return (
    <Badge
      variant="outline"
      className={
        t.label === "growth"
          ? "gap-1 text-emerald-700 dark:text-emerald-400"
          : t.label === "decline"
            ? "gap-1 text-red-700 dark:text-red-400"
            : "gap-1"
      }
    >
      {Icon && <Icon className="size-3" />}
      {titleCase(t.label)}
      {(t.label === "growth" || t.label === "decline") &&
        t.total_change_pct !== undefined &&
        t.total_change_pct !== null &&
        ` ${signedPct(t.total_change_pct)}`}
    </Badge>
  );
}

const rowsOf = (rows: GroupRow[], metric: string, label: (g: string) => string = titleCase) =>
  rows
    .filter((r) => typeof r[metric] === "number")
    .map((r) => ({ label: label(r.group), value: r[metric] as number, low: r.low_sample, count: r.count }));

export function PlatformPanel({ platform, s, findings }: { platform: string; s: PlatformSection; findings: Finding[] }) {
  const m = s.kpis.metrics;
  const un = s.kpis.unavailable;
  const color = platformColor(platform);
  const exp = s.exposure_metric ?? "exposure";
  const weekly = s.trends.weekly.map((w) => ({ ...w, label: shortDate(w.week) }));
  const mine = findings.filter((f) => f.platform === platform);
  const scatter = (s.video.scatter ?? [])
    .filter((p) => p.duration !== null && p.completion !== null)
    .map((p) => ({ x: p.duration as number, y: p.completion as number }));

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Posts" value={num(m.total_posts)} sub={`${num(m.posts_per_week, 1)} per week`} />
        <StatCard
          label={`Median ${exp}`}
          value={compact(m.median_reach ?? m.median_views ?? null)}
          sub={
            m.total_reach !== undefined
              ? `${compact(m.total_reach)} total reach`
              : m.total_impressions !== undefined
                ? `${compact(m.total_impressions)} impressions`
                : m.total_views !== undefined
                  ? `${compact(m.total_views)} total views`
                  : undefined
          }
          help={`Exposure metric for ${titleCase(platform)}: ${exp}.`}
          unavailable={m.median_reach === undefined && m.median_views === undefined ? `No reach/views column in the export (exposure = ${exp}).` : undefined}
        />
        <StatCard
          label="Engagement rate"
          value={pct(m.median_engagement_rate, 2)}
          sub={`median per post · ${pct(m.engagement_rate, 2)} aggregate`}
          help={`(${s.kpis.engagement_components.join(" + ")}) / ${exp} × 100. Aggregate = total engagement / total ${exp}.`}
          unavailable={un.engagement_rate}
        />
        <StatCard
          label="Followers gained"
          value={compact(m.follower_growth)}
          help="Sum of per-post follows reported in the export."
          unavailable={un.follower_growth}
        />
        <StatCard
          label="Clicks"
          value={compact(m.total_clicks)}
          sub={m.ctr !== undefined ? `CTR ${pct(m.ctr, 2)}` : undefined}
          help="Link / website clicks. CTR = clicks / impressions × 100 (exposure when impressions are absent)."
          unavailable={un.total_clicks}
        />
        <StatCard label="Share rate" value={pct(m.share_rate, 2)} sub={`${compact(m.total_shares)} shares`} unavailable={un.share_rate} />
        <StatCard label="Save rate" value={pct(m.save_rate, 2)} sub={`${compact(m.total_saves)} saves`} unavailable={un.save_rate} />
        <StatCard
          label="Video completion"
          value={pct(m.median_completion_rate, 1)}
          sub={`${m.video_posts} videos`}
          unavailable={un.median_completion_rate}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-2">
              <div>
                <CardTitle>Weekly median {exp}</CardTitle>
                <CardDescription>Per-week median with a 3-week rolling average</CardDescription>
              </div>
              <TrendBadge t={s.trends.trends.median_exposure} />
            </div>
          </CardHeader>
          <CardContent>
            <TrendChart
              data={weekly}
              series={[
                { key: "median_exposure", label: `Weekly median ${exp}`, color },
                { key: "median_exposure_rolling3", label: "3-week rolling", color, dashed: true },
              ]}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-2">
              <div>
                <CardTitle>Weekly median engagement rate</CardTitle>
                <CardDescription>Theil-Sen trend, Spearman-tested</CardDescription>
              </div>
              <TrendBadge t={s.trends.trends.median_er} />
            </div>
          </CardHeader>
          <CardContent>
            <TrendChart
              data={weekly}
              format={(v) => `${num(v, 1)}%`}
              series={[
                { key: "median_er", label: "Weekly median ER", color },
                { key: "median_er_rolling3", label: "3-week rolling", color, dashed: true },
              ]}
            />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Content formats</CardTitle>
            <CardDescription>Median engagement rate by format · faded = fewer than 5 posts</CardDescription>
          </CardHeader>
          <CardContent>
            <HBarChart rows={rowsOf(s.formats.formats, "median_er", formatLabel)} color={color} format={(v) => `${num(v, 2)}%`} />
            <Table className="mt-2">
              <TableHeader>
                <TableRow>
                  <TableHead>Format</TableHead>
                  <TableHead className="text-right">Posts</TableHead>
                  <TableHead className="text-right">Median {exp}</TableHead>
                  <TableHead className="text-right">Median ER</TableHead>
                  <TableHead className="text-right">Perf. index</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {s.formats.formats.map((r) => (
                  <TableRow key={r.group}>
                    <TableCell>{formatLabel(r.group)}</TableCell>
                    <TableCell className="text-right tabular-nums">{r.count}</TableCell>
                    <TableCell className="text-right tabular-nums">{compact(r.median_exposure as number)}</TableCell>
                    <TableCell className="text-right tabular-nums">{pct(r.median_er as number, 2)}</TableCell>
                    <TableCell className="text-right tabular-nums">{num(r.median_performance_index as number, 0)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Posting days</CardTitle>
            <CardDescription>
              Median ER by day of week (within this dataset - not a universal best time)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ColumnChart
              rows={rowsOf(s.timing.by_day, "median_er", (g) => g.slice(0, 3))}
              color={color}
              format={(v) => `${num(v, 1)}%`}
            />
            {s.timing.has_time ? (
              <div>
                <p className="mb-1 text-xs font-medium text-muted-foreground">By time of day</p>
                <HBarChart rows={rowsOf(s.timing.by_hour_block, "median_er")} color={color} format={(v) => `${num(v, 2)}%`} />
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">{s.timing.note}</p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Posting consistency</CardTitle>
            <CardDescription>{s.posting.method}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">
                Score {num(s.posting.consistency_score)} / 100 · {s.posting.consistency}
              </Badge>
              <Badge variant="outline">Longest gap: {s.posting.longest_gap_days} days</Badge>
              <Badge variant="outline">Active weeks: {pct(s.posting.active_weeks_pct, 0)}</Badge>
            </div>
            <ColumnChart
              rows={s.posting.weekly_counts.map((w) => ({ label: shortDate(w.week), value: w.posts }))}
              color={color}
              format={(v) => num(v)}
              height={160}
            />
            {s.posting.inactivity_periods.length > 0 && (
              <p className="text-xs text-muted-foreground">
                Inactive periods:{" "}
                {s.posting.inactivity_periods.map((g) => `${shortDate(g.from)} (${g.days} days)`).join(", ")}
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Video performance</CardTitle>
            <CardDescription>
              {s.video.video_count >= 5
                ? `${s.video.video_count} videos · median completion ${pct(s.video.median_completion, 1)} · median length ${num(s.video.median_duration_seconds)}s`
                : (s.video.note ?? "Too few videos")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {scatter.length >= 5 ? (
              <ScatterPlot points={scatter} color={color} xLabel="Duration (s)" yLabel="Completion %" />
            ) : s.video.by_duration?.length ? (
              <HBarChart rows={rowsOf(s.video.by_duration, "median_exposure")} color={color} format={compact} />
            ) : (
              <p className="py-8 text-center text-sm text-muted-foreground">No video duration or completion data.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {s.statistics.regression && (
        <Card>
          <CardHeader>
            <CardTitle>Multivariate model</CardTitle>
            <CardDescription>
              {s.statistics.regression.model} · n = {s.statistics.regression.n} · R² ={" "}
              {num(s.statistics.regression.r_squared, 2)} (adj. {num(s.statistics.regression.adj_r_squared, 2)})
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Term</TableHead>
                  <TableHead className="text-right">Effect vs. baseline</TableHead>
                  <TableHead className="text-right">Std. error</TableHead>
                  <TableHead className="text-right">p-value</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {s.statistics.regression.terms.map((t) => (
                  <TableRow key={t.term} className={t.p_value < 0.05 ? "" : "text-muted-foreground"}>
                    <TableCell>{titleCase(t.term.replace("content_", "").replace("=", ": "))}</TableCell>
                    <TableCell className="text-right tabular-nums">{signedPct(t.pct_effect, 0)}</TableCell>
                    <TableCell className="text-right tabular-nums">{num(t.std_err, 3)}</TableCell>
                    <TableCell className="text-right tabular-nums">{t.p_value < 0.001 ? "<0.001" : num(t.p_value, 3)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="mt-2 text-xs text-muted-foreground">
              Baselines: {Object.entries(s.statistics.regression.baselines).map(([k, v]) => `${titleCase(k)} = ${v}`).join(" · ")}.{" "}
              {s.statistics.regression.interpretation}
            </p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Statistical findings</CardTitle>
          <CardDescription>
            Non-parametric tests with Benjamini-Hochberg correction; each carries its confidence level.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <FindingsList findings={mine} />
        </CardContent>
      </Card>
    </div>
  );
}
