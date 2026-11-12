import { api } from "@/lib/api";
import type {
  AIOutput,
  AnalyticsRun,
  AuditContent,
  CanonicalField,
  ContentPlanContent,
  DemoBusiness,
  FilePreview,
  NormalizeResponse,
  Platform,
  Project,
  ProjectCreate,
  StrategyContent,
  UploadedFile,
} from "@/types/api";

/** SWR keys (API paths) used across pages, so mutations can revalidate them. */
export const keys = {
  projects: "/projects",
  project: (id: string) => `/projects/${id}`,
  files: (id: string) => `/projects/${id}/files`,
  file: (id: string, fileId: string) => `/projects/${id}/files/${fileId}`,
  preview: (id: string, fileId: string) => `/projects/${id}/files/${fileId}/preview?limit=8`,
  analytics: (id: string, version?: number) => `/projects/${id}/analytics${version ? `?version=${version}` : ""}`,
  runs: (id: string) => `/projects/${id}/analytics/runs`,
  insights: (id: string) => `/projects/${id}/insights`,
  posts: (id: string, qs: string) => `/projects/${id}/posts?${qs}`,
  audit: (id: string) => `/projects/${id}/audit`,
  strategy: (id: string) => `/projects/${id}/strategy`,
  plan: (id: string) => `/projects/${id}/content-plan`,
  canonicalFields: "/meta/canonical-fields",
  demoBusinesses: "/demo/businesses",
};

export const projectsApi = {
  create: (data: ProjectCreate) => api.post<Project>("/projects", data),
  update: (id: string, data: Partial<ProjectCreate>) => api.put<Project>(`/projects/${id}`, data),
  remove: (id: string) => api.delete(`/projects/${id}`),

  upload: (id: string, files: File[], platform?: Platform | null) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    if (platform) form.append("platform", platform);
    return api.post<UploadedFile[]>(`/projects/${id}/files`, form);
  },
  removeFile: (id: string, fileId: string) => api.delete(`/projects/${id}/files/${fileId}`),
  preview: (id: string, fileId: string) => api.get<FilePreview>(`/projects/${id}/files/${fileId}/preview?limit=8`),
  detectMapping: (id: string, fileId: string, platform?: Platform | null) =>
    api.post<UploadedFile>(`/projects/${id}/files/${fileId}/mapping/detect`, { platform: platform ?? null }),
  confirmMapping: (
    id: string,
    fileId: string,
    platform: Platform,
    mappings: { source_column: string; target_field: string | null }[],
  ) => api.post<UploadedFile>(`/projects/${id}/files/${fileId}/mapping/confirm`, { platform, mappings }),
  normalize: (id: string) => api.post<NormalizeResponse>(`/projects/${id}/normalize`),
  analyze: (id: string) => api.post<AnalyticsRun>(`/projects/${id}/analyze`),

  generateAudit: (id: string, instructions?: string, useAi = true) =>
    api.post<AIOutput<AuditContent>>(`/projects/${id}/audit`, { instructions: instructions || null, use_ai: useAi }),
  generateStrategy: (id: string, instructions?: string, useAi = true) =>
    api.post<AIOutput<StrategyContent>>(`/projects/${id}/strategy`, { instructions: instructions || null, use_ai: useAi }),
  generatePlan: (id: string, instructions?: string, startDate?: string, useAi = true) =>
    api.post<AIOutput<ContentPlanContent>>(`/projects/${id}/content-plan`, {
      instructions: instructions || null,
      start_date: startDate || null,
      use_ai: useAi,
    }),
  classify: (id: string) => api.post<{ posts_updated: number; note: string }>(`/projects/${id}/classify`),

  demo: (business = "agency_uae", days = 90, seed = 42) =>
    api.post<Project>("/demo/generate", { business, days, seed }),
};

export type { CanonicalField, DemoBusiness };
