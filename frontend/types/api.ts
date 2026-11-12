/** Types mirroring the backend API (app/schemas/*.py and analytics section payloads). */

export type Platform = "instagram" | "facebook" | "tiktok" | "linkedin";
export type Confidence = "high" | "medium" | "low";
export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface ApiErrorBody {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface ComponentStatus {
  status: "ok" | "error" | "not_configured";
  detail: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  app: string;
  version: string;
  environment: string;
  database: ComponentStatus;
  ai: ComponentStatus;
}

// ---------------------------------------------------------------- projects
export type MarketingObjective =
  | "brand_awareness"
  | "engagement"
  | "lead_generation"
  | "sales"
  | "website_traffic"
  | "store_visits"
  | "community_growth"
  | "follower_growth"
  | "video_views";

export type ProjectStatus =
  | "draft"
  | "data_uploaded"
  | "normalized"
  | "analyzed"
  | "audited"
  | "strategy_ready";

export interface BusinessProfile {
  business_name: string;
  industry: string;
  country: string;
  city_market: string | null;
  products_services: string;
  target_audience: string;
  business_objective: string;
  marketing_objectives: MarketingObjective[];
  competitors: string[];
  monthly_budget: string | number | null;
  budget_currency: string | null;
  current_posting_frequency: string | null;
  additional_instructions: string | null;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  platforms: Platform[];
  timezone: string;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
  business_profile: (BusinessProfile & { id: string }) | null;
}

export interface HeadlinePlatform {
  posts: number;
  exposure_metric: string | null;
  median_exposure: number | null;
  engagement_rate: number | null;
  median_engagement_rate: number | null;
  follower_growth: number | null;
  total_clicks: number | null;
  total_views: number | null;
  total_reach: number | null;
  posts_per_week: number | null;
  consistency: string;
  exposure_trend: string | null;
}

export interface Headline {
  total_posts: number;
  platforms: Record<string, HeadlinePlatform>;
  insight_counts: { negative: number; positive: number; high_severity: number };
  findings: { total: number; significant: number; high_confidence: number };
}

export interface ProjectListItem extends Project {
  files: { count: number; platforms: Platform[] };
  post_count: number;
  latest_run: {
    id: string;
    analysis_version: number;
    status: string;
    finished_at: string | null;
    post_count: number;
    headline: Partial<Headline>;
  } | null;
  has_audit: boolean;
  has_strategy: boolean;
}

export interface ProjectCreate {
  name: string;
  description?: string | null;
  platforms: Platform[];
  timezone: string;
  business_profile: Omit<BusinessProfile, "monthly_budget"> & { monthly_budget: number | null };
}

// ---------------------------------------------------------------- files & mapping
export interface ColumnProfile {
  name: string;
  inferred_type: string;
  null_pct: number;
  unique_count: number;
  numeric_ratio: number;
  sample_values: string[];
}

export interface ColumnMapping {
  source_column: string;
  target_field: string | null;
  confidence: number;
  method: "exact" | "fuzzy" | "manual" | "unmapped";
  needs_review: boolean;
  confirmed: boolean;
  alternatives: { field: string; score: number }[];
}

export interface ValidationIssue {
  code: string;
  severity: "error" | "warning" | "info";
  message: string;
  column: string | null;
  count: number;
  examples: string[];
}

export interface UploadedFile {
  id: string;
  project_id: string;
  original_filename: string;
  file_type: string;
  size_bytes: number;
  status: "uploaded" | "mapped" | "normalized" | "failed";
  row_count: number | null;
  column_count: number | null;
  header_row: number;
  sheet_name: string | null;
  columns: ColumnProfile[];
  platform: Platform | null;
  detected_platform: Platform | null;
  detection_confidence: number | null;
  validation: {
    stage?: string;
    is_valid?: boolean;
    rows_in?: number;
    rows_valid?: number;
    rows_dropped?: number;
    issues?: ValidationIssue[];
    detection_scores?: Record<string, number>;
  };
  posts_imported: number | null;
  created_at: string;
  mappings: ColumnMapping[];
}

export interface FilePreview {
  columns: string[];
  rows: Record<string, string | null>[];
  total_rows: number;
}

export interface CanonicalField {
  name: string;
  label: string;
  type: string;
  required: boolean;
}

export interface NormalizeResponse {
  files: {
    file_id: string;
    filename: string;
    platform: Platform | null;
    status: string;
    posts_imported: number;
    validation: UploadedFile["validation"];
  }[];
  total_posts: number;
}

// ---------------------------------------------------------------- analytics
export interface AnalyticsRun {
  id: string;
  project_id: string;
  analysis_version: number;
  status: "running" | "completed" | "failed";
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  post_count: number;
  period_start: string | null;
  period_end: string | null;
  parameters: {
    objectives?: string[];
    weights?: Record<string, number>;
    weights_explanation?: string;
    alpha?: number;
    [k: string]: unknown;
  };
  summary: { headline?: Headline };
  error: string | null;
  created_at: string;
}

export interface GroupRow {
  group: string;
  label?: string;
  count: number;
  share_pct: number;
  low_sample: boolean;
  [metric: string]: string | number | boolean | undefined | null;
}

export interface PostCard {
  post_id: string | null;
  external_post_id: string;
  platform: Platform;
  published_at: string | null;
  format: string | null;
  pillar: string | null;
  topic: string | null;
  hook_type: string | null;
  cta_type: string | null;
  caption: string;
  permalink: string | null;
  exposure: number | null;
  engagement: number | null;
  er: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  saves: number | null;
  clicks: number | null;
  views: number | null;
  completion: number | null;
  video_duration_seconds: number | null;
  performance_index: number | null;
  z_score?: number;
}

export interface TrendInfo {
  label: "growth" | "decline" | "plateau" | "volatile" | "insufficient_data";
  weeks: number;
  total_change_pct?: number | null;
  pct_change_per_week?: number | null;
  p_value?: number | null;
  cv?: number | null;
}

export interface WeeklyPoint {
  week: string;
  complete: boolean;
  posts?: number | null;
  median_exposure?: number | null;
  median_er?: number | null;
  total_engagement?: number | null;
  followers_gained?: number | null;
  median_completion?: number | null;
  median_exposure_rolling3?: number | null;
  median_er_rolling3?: number | null;
  [k: string]: string | number | boolean | null | undefined;
}

export interface PlatformSection {
  exposure_metric: string | null;
  kpis: {
    exposure_metric: string | null;
    engagement_components: string[];
    metrics: Record<string, number>;
    unavailable: Record<string, string>;
    completeness: Record<string, number>;
  };
  posting: {
    posts: number;
    posts_per_week: number | null;
    posts_per_month: number | null;
    active_weeks_pct: number | null;
    weekly_counts: { week: string; posts: number }[];
    weekly_cv: number | null;
    median_days_between_posts: number | null;
    longest_gap_days: number;
    inactivity_periods: { from: string; days: number }[];
    consistency_score: number | null;
    consistency: "high" | "moderate" | "low";
    method: string;
  };
  formats: { formats: GroupRow[]; format_count: number };
  pillars: {
    pillar_distribution: Record<string, number>;
    topic_distribution: Record<string, number>;
    pillars: GroupRow[];
    topics: GroupRow[];
    pillar_diversity: number | null;
    format_diversity: number | null;
    classification: { source_counts: Record<string, number>; low_confidence_share: number | null };
  };
  hooks_ctas: {
    cta_usage_pct: number | null;
    cta_distribution: Record<string, number>;
    hook_distribution: Record<string, number>;
    hooks: GroupRow[];
    ctas: GroupRow[];
  };
  timing: {
    has_time: boolean;
    by_day: GroupRow[];
    by_hour_block: GroupRow[];
    weekday_vs_weekend: GroupRow[];
    posting_hours: Record<string, number>;
    note?: string;
  };
  trends: { weekly: WeeklyPoint[]; trends: Record<string, TrendInfo> };
  video: {
    video_count: number;
    median_completion?: number | null;
    median_duration_seconds?: number | null;
    video_share_of_posts?: number | null;
    by_duration?: GroupRow[];
    scatter?: { duration: number | null; completion: number | null; exposure: number | null }[];
    note?: string;
  };
  statistics: {
    correlations: { x: string; y: string; rho: number; p_value: number; n: number }[];
    regression: {
      model: string;
      n: number;
      r_squared: number;
      adj_r_squared: number;
      baselines: Record<string, string>;
      terms: { term: string; coef: number; pct_effect: number; std_err: number; p_value: number }[];
      interpretation: string;
    } | null;
  };
  top_content: Record<string, PostCard[] | number | string | null>;
  anomalies: {
    method: string;
    metrics: Record<string, { over_performers: PostCard[]; under_performers: PostCard[]; iqr_outlier_count: number }>;
    outlier_share_pct: number | null;
  };
  audience: {
    interaction_mix_pct: Record<string, number>;
    comment_rate_median: number | null;
    save_to_share_ratio: number | null;
    followers_per_1k_exposure: number | null;
    clicks_per_1k_exposure: number | null;
    signals: { signal: string; description: string; evidence: Record<string, unknown> }[];
    limitations: string;
  };
}

export interface Finding {
  id: string;
  category: string;
  platform: Platform | null;
  statement: string;
  metric: string;
  values: Record<string, unknown>;
  sample_size: number;
  p_value: number | null;
  p_adjusted: number | null;
  effect_size: number | null;
  effect_size_label: string | null;
  difference_pct: number | null;
  method: string;
  confidence: Confidence;
  confidence_reasons: string[];
  limitations: string[];
  significant: boolean | null;
}

export interface CrossPlatformRow {
  platform: Platform;
  label: string;
  exposure_metric: string | null;
  posts: number;
  share_of_posts_pct: number | null;
  posts_per_week: number | null;
  consistency_score: number | null;
  median_er: number | null;
  aggregate_er: number | null;
  clicks_total: number | null;
  clicks_per_1k_exposure: number | null;
  follows_per_1k_exposure: number | null;
  follower_growth: number | null;
  share_rate_median: number | null;
  video_posts: number;
  median_video_completion: number | null;
  exposure_trend: string | null;
  exposure_trend_pct: number | null;
  er_trend: string | null;
}

export interface CrossPlatformAnswer {
  platform: Platform;
  label: string;
  value?: number | null;
  metric?: string;
  reason?: string;
  ranking?: { platform: Platform; value: number | null }[];
}

export interface PostMetric {
  id: string | null;
  platform: Platform;
  external_post_id: string | null;
  published_at: string;
  content_format: string | null;
  content_pillar: string | null;
  content_topic: string | null;
  hook_type: string | null;
  cta_type: string | null;
  exposure: number | null;
  engagement_total: number | null;
  er: number | null;
  share_rate: number | null;
  save_rate: number | null;
  click_rate: number | null;
  completion: number | null;
  video_duration_seconds: number | null;
  performance_index: number | null;
  caption: string;
}

export interface AnalyticsSections {
  overview: {
    period_start: string;
    period_end: string;
    period_days: number;
    total_posts: number;
    posts_by_platform: Record<string, number>;
    exposure_metric_by_platform: Record<string, string | null>;
    engagement_components_by_platform: Record<string, string[]>;
    data_completeness_by_platform: Record<string, Record<string, number>>;
  };
  platforms: Record<string, PlatformSection>;
  overall: { kpis: Record<string, unknown>; pillars: PlatformSection["pillars"] };
  cross_platform: {
    methodology: string;
    platforms: CrossPlatformRow[];
    answers: Record<string, CrossPlatformAnswer | null>;
    normalized_scores: { platform: Platform; label: string; scores: Record<string, number>; overall: number | null }[];
  };
  scoring: { method: string; weights: Record<string, number>; weights_explanation: string; [k: string]: unknown };
  post_metrics: PostMetric[];
  findings: Finding[];
}

export interface AnalyticsRead {
  run: AnalyticsRun;
  sections: Partial<AnalyticsSections>;
}

export interface Insight {
  id: string;
  rule_id: string;
  category: string;
  platform: Platform | null;
  title: string;
  description: string;
  metric: string | null;
  evidence: Record<string, unknown>;
  confidence: Confidence;
  severity: Severity;
  sentiment: "positive" | "negative" | "neutral";
  recommendation_hint: string | null;
}

export interface InsightList {
  analysis_version: number;
  insights: Insight[];
}

export interface Post {
  id: string;
  platform: Platform;
  external_post_id: string;
  published_at: string;
  permalink: string | null;
  content_format: string | null;
  caption: string | null;
  hashtags: string[];
  content_topic: string | null;
  content_pillar: string | null;
  topic_source: string | null;
  topic_confidence: number | null;
  cta_type: string | null;
  hook_type: string | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  saves: number | null;
  views: number | null;
  reach: number | null;
  impressions: number | null;
  clicks: number | null;
  website_clicks: number | null;
  followers_gained: number | null;
  video_duration_seconds: number | null;
  completion_rate: number | null;
}

export interface PostPage {
  total: number;
  items: Post[];
}

// ---------------------------------------------------------------- AI outputs
export type Level = "high" | "medium" | "low";
export type PlatformOrAll = Platform | "all";

export interface AuditPoint {
  title: string;
  explanation: string;
  evidence: string;
  evidence_refs: string[];
  platform: PlatformOrAll;
  impact: Level;
  confidence: Level;
  basis: "data_backed" | "general_best_practice";
}

export interface Recommendation extends AuditPoint {
  priority: "critical" | "high" | "medium" | "low";
  effort: Level;
}

export interface Verification {
  status: "verified" | "needs_review" | "deterministic";
  numbers_checked?: number;
  unverified_count?: number;
  issues?: { path: string; unverified_numbers: number[]; text: string }[];
  method?: string;
}

export interface AuditContent {
  executive_summary: string;
  overall_findings: AuditPoint[];
  platform_audits: {
    platform: PlatformOrAll;
    summary: string;
    performance_assessment: string;
    strengths: string[];
    weaknesses: string[];
    data_limitations: string[];
  }[];
  strengths: AuditPoint[];
  weaknesses: AuditPoint[];
  opportunities: AuditPoint[];
  risks: AuditPoint[];
  content_gaps: AuditPoint[];
  best_content_patterns: AuditPoint[];
  worst_content_patterns: AuditPoint[];
  audience_insights: AuditPoint[];
  priority_actions: Recommendation[];
  data_limitations: string[];
  _verification?: Verification;
}

export interface StrategyContent {
  strategy_summary: string;
  strategic_objectives: { objective: string; kpi: string; target: string; timeframe: string }[];
  platform_strategies: {
    platform: PlatformOrAll;
    role: string;
    goal: string;
    formats: string[];
    posting_frequency: string;
    content_mix: { pillar: string; share_pct: number }[];
    hook_guidance: string;
    cta_approach: string;
    video_guidance: string;
    community_approach: string;
    rationale: string;
    evidence_refs: string[];
  }[];
  content_pillars: {
    name: string;
    description: string;
    target_share_pct: number;
    rationale: string;
    example_topics: string[];
  }[];
  format_strategy: string;
  video_strategy: string;
  caption_strategy: string;
  cta_strategy: string;
  community_strategy: string;
  growth_strategy: string;
  audience_strategy: string;
  measurement_plan: {
    kpi: string;
    platform: PlatformOrAll;
    definition: string;
    baseline: string;
    target_direction: string;
    review_cadence: string;
  }[];
  action_plan_30_days: { week: number; focus: string; actions: string[] }[];
  recommendations: Recommendation[];
  assumptions: string[];
  _verification?: Verification;
}

export interface ContentPlanEntry {
  day: number;
  date: string | null;
  platform: PlatformOrAll;
  pillar: string;
  format: string;
  topic: string;
  hook: string;
  concept: string;
  cta: string;
  objective: string;
  kpi: string;
}

export interface ContentPlanContent {
  plan_summary: string;
  entries: ContentPlanEntry[];
  ideas: {
    title: string;
    platform: PlatformOrAll;
    format: string;
    pillar: string;
    hook: string;
    concept: string;
    caption_direction: string;
    cta: string;
    goal: string;
    based_on: string;
  }[];
  notes: string[];
  start_date?: string;
  _verification?: Verification;
}

export interface AIOutput<T> {
  id: string;
  project_id: string;
  analytics_run_id: string;
  version: number;
  generated_by: "llm" | "rules";
  provider: string | null;
  model: string | null;
  user_instructions: string | null;
  content: T;
  created_at: string;
}

// ---------------------------------------------------------------- demo
export interface DemoBusiness {
  key: string;
  business_name: string;
  industry: string;
  country: string;
  city_market: string;
  marketing_objectives: string[];
  platforms: Platform[];
  posts_per_90_days: Record<string, number>;
}
