import type { Platform } from "@/types/api";

export const PLATFORMS: Platform[] = ["instagram", "facebook", "tiktok", "linkedin"];

export const PLATFORM_LABEL: Record<string, string> = {
  instagram: "Instagram",
  facebook: "Facebook",
  tiktok: "TikTok",
  linkedin: "LinkedIn",
  all: "All platforms",
};

export const platformColor = (p: string) => `var(--platform-${p}, var(--series-1))`;
export const seriesColor = (i: number) => `var(--series-${(i % 8) + 1})`;

const FORMAT_LABEL: Record<string, string> = {
  reel: "Reels",
  carousel: "Carousels",
  image: "Images",
  video: "Videos",
  short_video: "Short videos",
  text: "Text posts",
  link: "Link posts",
  document: "Documents",
  story: "Stories",
  other: "Other",
};

export const formatLabel = (f: string | null | undefined) => (f ? (FORMAT_LABEL[f] ?? titleCase(f)) : "—");

export function titleCase(s: string | null | undefined): string {
  if (!s) return "—";
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function compact(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

export function num(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(n);
}

export function pct(n: number | null | undefined, digits = 1): string {
  return n === null || n === undefined || Number.isNaN(n) ? "—" : `${num(n, digits)}%`;
}

export function signedPct(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${n > 0 ? "+" : ""}${num(n, digits)}%`;
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en", { month: "short", day: "numeric" });
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en", { dateStyle: "medium", timeStyle: "short" });
}

export const OBJECTIVES = [
  { value: "brand_awareness", label: "Brand awareness" },
  { value: "engagement", label: "Engagement" },
  { value: "lead_generation", label: "Lead generation" },
  { value: "sales", label: "Sales" },
  { value: "website_traffic", label: "Website traffic" },
  { value: "store_visits", label: "Store visits" },
  { value: "community_growth", label: "Community growth" },
  { value: "follower_growth", label: "Follower growth" },
  { value: "video_views", label: "Video views" },
] as const;
