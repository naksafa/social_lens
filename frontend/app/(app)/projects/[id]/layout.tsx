"use client";

import {
  BarChart3,
  CalendarDays,
  ClipboardCheck,
  Database,
  FileText,
  Home,
  LayoutGrid,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { PlatformBadge } from "@/components/project/badges";
import { ErrorState } from "@/components/project/states";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useProject } from "@/hooks/use-api";
import { titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

const TABS = [
  { seg: "", label: "Overview", icon: Home },
  { seg: "data", label: "Data", icon: Database },
  { seg: "analytics", label: "Analytics", icon: BarChart3 },
  { seg: "content", label: "Content", icon: LayoutGrid },
  { seg: "audit", label: "Audit", icon: ClipboardCheck },
  { seg: "strategy", label: "Strategy", icon: Target },
  { seg: "plan", label: "30-day plan", icon: CalendarDays },
  { seg: "report", label: "Report", icon: FileText },
];

export default function ProjectLayout({ children }: { children: ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const pathname = usePathname();
  const { data: project, error } = useProject(id);
  const base = `/projects/${id}`;

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6">
        {error ? (
          <ErrorState error={error} />
        ) : !project ? (
          <Skeleton className="h-12 w-80" />
        ) : (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <h1 className="text-2xl font-semibold tracking-tight">
              {project.business_profile?.business_name ?? project.name}
            </h1>
            <Badge variant="secondary">{titleCase(project.status)}</Badge>
            {project.is_demo && <Badge variant="outline">Demo data</Badge>}
            <div className="flex flex-wrap gap-1.5">
              {project.platforms.map((p) => (
                <PlatformBadge key={p} platform={p} />
              ))}
            </div>
          </div>
        )}
        {project?.business_profile && (
          <p className="mt-1 text-sm text-muted-foreground">
            {project.business_profile.industry} · {project.business_profile.city_market ?? project.business_profile.country}
          </p>
        )}
      </div>

      <nav className="-mx-4 mb-8 overflow-x-auto border-b px-4 md:mx-0 md:px-0" aria-label="Project sections">
        <ul className="flex min-w-max gap-1">
          {TABS.map(({ seg, label, icon: Icon }) => {
            const href = seg ? `${base}/${seg}` : base;
            const active = seg ? pathname.startsWith(href) : pathname === base;
            return (
              <li key={seg}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "-mb-px flex items-center gap-1.5 border-b-2 border-transparent px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:text-foreground",
                    active && "border-primary font-medium text-foreground",
                  )}
                >
                  <Icon className="size-4" />
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      {children}
    </div>
  );
}
