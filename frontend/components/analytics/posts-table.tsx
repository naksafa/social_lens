"use client";

import { ChevronLeft, ChevronRight, Download } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { apiUrl } from "@/lib/api";
import { compact, formatLabel, PLATFORM_LABEL, shortDate, titleCase } from "@/lib/format";
import { keys } from "@/services/projects";
import type { PostPage } from "@/types/api";

const SORTS = {
  published_at: "Newest",
  reach: "Reach",
  views: "Views",
  impressions: "Impressions",
  likes: "Likes",
  comments: "Comments",
  shares: "Shares",
  saves: "Saves",
  clicks: "Clicks",
};
const PAGE = 25;

export function PostsTable({ projectId, platforms }: { projectId: string; platforms: string[] }) {
  const [platform, setPlatform] = useState("all");
  const [sort, setSort] = useState("published_at");
  const [page, setPage] = useState(0);
  const qs = new URLSearchParams({ sort, limit: String(PAGE), offset: String(page * PAGE) });
  if (platform !== "all") qs.set("platform", platform);
  const { data } = useApi<PostPage>(keys.posts(projectId, qs.toString()));
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;
  const platformItems = { all: "All platforms", ...Object.fromEntries(platforms.map((p) => [p, PLATFORM_LABEL[p]])) };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Select items={platformItems} value={platform} onValueChange={(v) => { setPlatform(v ?? "all"); setPage(0); }}>
          <SelectTrigger size="sm" className="w-40" aria-label="Filter by platform">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(platformItems).map(([v, l]) => (
              <SelectItem key={v} value={v}>
                {l}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select items={SORTS} value={sort} onValueChange={(v) => { setSort(v ?? "published_at"); setPage(0); }}>
          <SelectTrigger size="sm" className="w-36" aria-label="Sort by">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(SORTS).map(([v, l]) => (
              <SelectItem key={v} value={v}>
                Sort: {l}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <a href={apiUrl(`/projects/${projectId}/export/posts.csv`)} className={buttonVariants({ variant: "outline", size: "sm" })}>
          <Download /> Export CSV
        </a>
        <span className="ml-auto text-xs text-muted-foreground">{data?.total ?? "…"} posts</span>
      </div>
      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="pl-3">Post</TableHead>
              <TableHead>Platform</TableHead>
              <TableHead>Format</TableHead>
              <TableHead>Topic / pillar</TableHead>
              <TableHead className="text-right">Reach / views</TableHead>
              <TableHead className="text-right">Likes</TableHead>
              <TableHead className="text-right">Comments</TableHead>
              <TableHead className="text-right">Shares</TableHead>
              <TableHead className="text-right">Saves</TableHead>
              <TableHead className="pr-3 text-right">Clicks</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data?.items ?? []).map((p) => (
              <TableRow key={p.id}>
                <TableCell className="max-w-72 pl-3">
                  <p className="truncate text-sm" title={p.caption ?? ""}>
                    {p.caption || "—"}
                  </p>
                  <p className="text-xs text-muted-foreground">{shortDate(p.published_at)}</p>
                </TableCell>
                <TableCell>{PLATFORM_LABEL[p.platform]}</TableCell>
                <TableCell>{formatLabel(p.content_format)}</TableCell>
                <TableCell>
                  <span className="text-sm">{titleCase(p.content_topic)}</span>
                  <p className="text-xs text-muted-foreground">
                    {titleCase(p.content_pillar)}
                    {p.topic_source && (
                      <Badge variant="outline" className="ml-1 h-4 px-1 text-[10px] font-normal">
                        {p.topic_source}
                      </Badge>
                    )}
                  </p>
                </TableCell>
                <TableCell className="text-right tabular-nums">{compact(p.reach ?? p.views ?? p.impressions)}</TableCell>
                <TableCell className="text-right tabular-nums">{compact(p.likes)}</TableCell>
                <TableCell className="text-right tabular-nums">{compact(p.comments)}</TableCell>
                <TableCell className="text-right tabular-nums">{compact(p.shares)}</TableCell>
                <TableCell className="text-right tabular-nums">{compact(p.saves)}</TableCell>
                <TableCell className="pr-3 text-right tabular-nums">{compact(p.clicks ?? p.website_clicks)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-end gap-2 text-sm">
        <Button variant="outline" size="icon-sm" aria-label="Previous page" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
          <ChevronLeft />
        </Button>
        <span className="tabular-nums text-muted-foreground">
          {page + 1} / {pages}
        </span>
        <Button variant="outline" size="icon-sm" aria-label="Next page" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>
          <ChevronRight />
        </Button>
      </div>
    </div>
  );
}
