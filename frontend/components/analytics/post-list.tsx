import { ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { compact, formatLabel, num, pct, shortDate, titleCase } from "@/lib/format";
import type { PostCard } from "@/types/api";

export function PostList({ posts, metric }: { posts: PostCard[]; metric: keyof PostCard }) {
  if (!posts.length) return <p className="py-6 text-center text-sm text-muted-foreground">No eligible posts.</p>;
  return (
    <ol className="divide-y">
      {posts.map((p, i) => {
        const v = p[metric];
        const shown =
          metric === "er" || metric === "completion" ? pct(v as number, metric === "er" ? 2 : 1) : compact(v as number);
        return (
          <li key={p.external_post_id + i} className="flex gap-3 py-2.5">
            <span className="mt-0.5 w-5 shrink-0 text-right text-xs text-muted-foreground tabular-nums">{i + 1}</span>
            <div className="min-w-0 flex-1">
              <p className="line-clamp-2 text-sm">{p.caption || <span className="text-muted-foreground">(no caption)</span>}</p>
              <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                <Badge variant="outline" className="font-normal">{formatLabel(p.format)}</Badge>
                {p.pillar && <Badge variant="outline" className="font-normal">{titleCase(p.pillar)}</Badge>}
                <span>{shortDate(p.published_at)}</span>
                <span>· {compact(p.exposure)} exposure</span>
                <span>· ER {pct(p.er, 2)}</span>
                {p.performance_index !== null && <span>· index {num(p.performance_index)}</span>}
                {p.permalink && (
                  <a href={p.permalink} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 hover:text-foreground">
                    open <ExternalLink className="size-3" />
                  </a>
                )}
              </div>
            </div>
            <span className="shrink-0 text-sm font-semibold tabular-nums">{shown}</span>
          </li>
        );
      })}
    </ol>
  );
}
