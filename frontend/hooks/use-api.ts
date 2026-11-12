"use client";

import useSWR, { type SWRConfiguration } from "swr";

import { fetcher } from "@/lib/api";
import { keys } from "@/services/projects";
import type {
  AIOutput,
  AnalyticsRead,
  AuditContent,
  CanonicalField,
  ContentPlanContent,
  DemoBusiness,
  InsightList,
  Project,
  ProjectListItem,
  StrategyContent,
  UploadedFile,
} from "@/types/api";

/** Thin SWR wrapper: `key = null` skips the request. 404s are surfaced as `error`. */
export function useApi<T>(key: string | null, config?: SWRConfiguration) {
  return useSWR<T>(key, fetcher, { revalidateOnFocus: false, shouldRetryOnError: false, ...config });
}

export const useProjects = () => useApi<ProjectListItem[]>(keys.projects);
export const useProject = (id: string) => useApi<Project>(keys.project(id));
export const useFiles = (id: string) => useApi<UploadedFile[]>(keys.files(id));
export const useAnalytics = (id: string, enabled = true) =>
  useApi<AnalyticsRead>(enabled ? keys.analytics(id) : null);
export const useInsights = (id: string) => useApi<InsightList>(keys.insights(id));
export const useAudit = (id: string) => useApi<AIOutput<AuditContent>>(keys.audit(id));
export const useStrategy = (id: string) => useApi<AIOutput<StrategyContent>>(keys.strategy(id));
export const usePlan = (id: string) => useApi<AIOutput<ContentPlanContent>>(keys.plan(id));
export const useCanonicalFields = () => useApi<CanonicalField[]>(keys.canonicalFields);
export const useDemoBusinesses = () => useApi<DemoBusiness[]>(keys.demoBusinesses);
