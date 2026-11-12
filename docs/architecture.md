# SocialLens AI — Architecture

## 1. Guiding principle

**Analytics first, AI second.** Every number shown to a user or given to an LLM is computed by
deterministic Python code, and every finding carries its sample size, evidence and confidence. The LLM
reads a compact, structured summary of those findings. It never reads raw exports, and a post-generation
check verifies that the numbers it writes exist in the data.

```
Raw CSV/XLSX
  → validation → platform detection → column mapping (fuzzy + confidence, user-correctable)
  → normalization (platform adapters) → cleaning → canonical posts + account snapshots
  → feature engineering → KPI engine → format / pillar / hook / CTA / timing / video analysis
  → trends → statistical tests (+ Benjamini-Hochberg) → confidence grading → rule-based insights
  → AnalyticsRun v{N} (immutable, versioned)                                     ◄── deterministic
  ──────────────────────────────────────────────────────────────────────────────────────────────
  → AnalyticsSummary (compact JSON) → Audit / Strategy / ContentPlan agents (structured outputs)
  → Pydantic validation (1 schema-correction retry) → numeric verification → stored v{N}
  → dashboard / HTML·PDF report                                                   ◄── AI
```

## 2. Components

| Layer | Tech | Responsibility |
|---|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind v4, shadcn/ui (Base UI), Recharts, SWR | Project wizard, upload and mapping, analytics dashboards, audit/strategy/plan views, report viewer |
| API | FastAPI, Pydantic v2 | REST endpoints, validation, structured errors, OpenAPI docs |
| Services | `app/services/` | Use-case orchestration (files, normalization, analysis pipeline, AI, demo) |
| Ingestion | pandas, rapidfuzz, openpyxl | Reading, profiling, detection, mapping, parsing, validation, adapters |
| Analytics | pandas, NumPy, SciPy | Features, KPIs, group comparisons, regression, trends, anomalies, scoring, insights |
| AI | Anthropic SDK, OpenAI SDK | Provider abstraction, prompt building, agents, verification, deterministic fallback |
| Persistence | PostgreSQL, SQLAlchemy 2.0 (sync), Alembic | Projects, files, posts, versioned runs and AI outputs, request logs |
| Storage | `StorageBackend` (local now, S3 later) | Uploaded files |
| Reporting | Jinja2 + inline SVG, optional WeasyPrint | Self-contained HTML report with print CSS; PDF in Docker |

## 3. Repository layout

```
sociallens-ai/
├── docker-compose.yml   .env.example   README.md
├── data/sample/                         synthetic native-format exports (Falcon Growth Studio)
├── docs/                                architecture.md, methodology.md
├── backend/
│   ├── alembic/                         migrations (initial schema)
│   ├── app/
│   │   ├── main.py                      app factory, middleware, error handlers
│   │   ├── api/routes/                  health, projects, files, analytics, ai, report, demo
│   │   ├── core/                        config, JSON logging + redaction, exceptions, enums, middleware
│   │   ├── db/                          Base, mixins, portable types, session
│   │   ├── models/                      project, file, post, analytics, ai
│   │   ├── schemas/                     Pydantic API schemas
│   │   ├── storage/                     StorageBackend, LocalStorage
│   │   ├── ingestion/                   readers, profiling, platform_detection, mapping, parsers,
│   │   │                                validation, normalizer, adapters/, field_aliases.json
│   │   ├── analytics/                   features, classification, kpi_engine, scoring, grouping,
│   │   │                                format_analysis, topic_analysis, timing_analysis,
│   │   │                                posting_frequency, trends, video_analysis, statistics,
│   │   │                                statistical_models, anomaly_detection, audience_analysis,
│   │   │                                cross_platform, confidence, findings, insights, engine, visual
│   │   ├── ai/                          base_provider, anthropic_provider, openai_provider, factory,
│   │   │                                prompts, prompt_builder, agents, schemas, guardrails, deterministic
│   │   ├── services/                    project, file, normalization, analysis_pipeline, ai, demo, jobs, posts
│   │   ├── reporting/                   report_service, charts (SVG), templates/report.html
│   │   ├── synthetic/                   profiles (3 demo businesses), captions, generator, exporters, cli
│   │   ├── integrations/                API source interfaces (Meta, TikTok, LinkedIn); planned
│   │   └── utils/                       files, serialization, csv_export (formula-injection safe)
│   └── tests/                           119 pytest tests
└── frontend/
    ├── app/(app)/                       dashboard, projects/new, projects/[id]/{data,analytics,content,
    │                                    audit,strategy,plan,report}
    ├── components/                      ui/ (shadcn), charts/, analytics/, project/, layout/, system/
    ├── hooks/ lib/ services/ types/
    └── __tests__/                       Vitest + Testing Library
```

## 4. Data model

| Table | Purpose |
|---|---|
| `projects`, `business_profiles`, `platform_accounts`, `users` | Project, business context and accounts (`users` / `owner_id` prepared for auth) |
| `uploaded_files`, `column_mappings` | Upload metadata, column profiles, detection, validation report, per-column mapping with confidence |
| `social_posts` | Canonical post: identity, text, classification (with source + confidence), 20 nullable metrics, multimodal fields (`thumbnail_url`, `media_url`, `visual_features`) |
| `metric_snapshots` | Account-level daily metrics (followers) |
| `analytics_runs` | Versioned, immutable analysis runs (input hash, parameters, headline) |
| `analytics_results` | JSON sections of a run (overview, platforms, cross_platform, scoring, post_metrics, findings) |
| `insights` | Rule-based insights per run |
| `ai_audits`, `marketing_strategies`, `content_plans` | Versioned AI outputs linked to the run they were built from (`generated_by`, provider, model, instructions) |
| `ai_request_logs` | Every LLM call: agent, provider, model, prompt hash and size, tokens, latency, attempts, success (never raw prompts or keys) |
| `content_classifications` | Cache of AI topic classifications by caption hash |

## 5. Request flow (per project)

1. `POST /projects`: business context and objectives.
2. `POST /projects/{id}/files`: upload is validated (extension, size), stored with a SHA-256
   (duplicates rejected), profiled, platform-detected and auto-mapped.
3. `POST /projects/{id}/files/{fid}/mapping/confirm`: user-corrected mapping, validated as a whole
   (required date, ≥ 1 metric, no duplicate targets).
4. `POST /projects/{id}/normalize`: each file's posts are replaced atomically. Overlaps between files
   are skipped and reported.
5. `POST /projects/{id}/analyze`: `AnalysisPipeline` runs `AnalysisEngine` (pure computation), stores a
   new run version, persists keyword classifications, and never overwrites old runs.
6. `POST /projects/{id}/audit` → `/strategy` → `/content-plan`: each agent reads a stored run. The
   outputs are versioned and each LLM call is logged.
7. `GET /projects/{id}/report`: the HTML (or `?format=pdf`) report is assembled from stored artifacts only.

## 6. API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | API, database and AI provider status |
| POST/GET | `/projects` | Create / list (with headline metrics) |
| GET/PUT/DELETE | `/projects/{id}` | Read / update / delete (cascades files and posts) |
| POST/GET | `/projects/{id}/files` | Upload (multipart, many files) / list |
| GET/DELETE | `/projects/{id}/files/{fid}` | File detail / remove |
| GET | `/projects/{id}/files/{fid}/preview` | First rows as parsed |
| POST | `/projects/{id}/files/{fid}/mapping/detect` | Re-detect (optionally for another platform) |
| POST | `/projects/{id}/files/{fid}/mapping/confirm` | Save the corrected mapping |
| POST | `/projects/{id}/normalize` | Import mapped files into canonical posts |
| POST | `/projects/{id}/analyze` | New analysis version (optional weight overrides) |
| GET | `/projects/{id}/analytics[?version=&sections=]` | Run metadata and result sections |
| GET | `/projects/{id}/analytics/runs` | All versions |
| GET | `/projects/{id}/insights` | Rule-based insights |
| GET | `/projects/{id}/posts` | Paginated, sortable, filterable posts |
| GET | `/projects/{id}/export/posts.csv` | CSV export (formula-injection safe) |
| POST/GET | `/projects/{id}/audit` | Generate / read (optional `version`) |
| POST/GET | `/projects/{id}/strategy` | Generate / read |
| POST/GET | `/projects/{id}/content-plan` | Generate / read (30 days + ideas) |
| POST | `/projects/{id}/classify` | AI re-classification of low-confidence posts (cached) |
| GET | `/projects/{id}/report[?format=pdf&download=true]` | Exportable report |
| GET/POST | `/demo/businesses`, `/demo/generate`, `/demo/dataset` | Demo mode and synthetic dataset download |
| GET | `/meta/canonical-fields`, `/meta/integrations` | Mapping targets; integration status |

All errors have the shape `{code, message, details}`.

## 7. AI layer

* **`LLMProvider`** (`base_provider.py`) exposes `generate`, `generate_structured` and `classify`. The base
  class owns validation and the single schema-correction retry. Providers implement `_generate` and
  `_structured` only. Registered providers are `AnthropicProvider` (default `claude-opus-5`: streaming,
  Pydantic structured outputs, adaptive thinking with configurable effort, server-side refusal fallbacks)
  and `OpenAIProvider` (Responses API with `text_format`). A new provider means one class plus one
  registry line.
* **Agents** (`agents.py`): `AuditAgent`, `StrategyAgent`, `ContentPlanAgent` and
  `ContentClassificationAgent`, each with its own system prompt (`prompts.py`) sharing common grounding rules.
* **Prompt payload** (`prompt_builder.py`): business context, verified analytics, and optional audit or
  strategy briefs, plus user instructions in tagged blocks. Typically 30–60k characters, never raw rows.
* **Guardrails** (`guardrails.py`): precision-aware numeric verification of the output against the payload.
* **Fallback** (`deterministic.py`): with no provider configured (or `use_ai=false`), the same schemas are
  composed from rule-based insights. The demo therefore works fully offline.

## 8. Cross-cutting concerns

* **Errors:** typed domain exceptions become structured JSON. Unhandled exceptions return a generic 500
  without leaking internals.
* **Logging:** JSON lines with request-id correlation. Fields named like keys, tokens or secrets are
  redacted, and inline `sk-…` keys are masked. Key events: `file.imported`, `mapping.*`,
  `normalization.*`, `analysis.started`/`completed`/`failed`, `ai.request`/`response`/`failed`,
  `report.*`.
* **Security:** secrets come from env only (`SecretStr`). Uploads are checked by extension and size,
  filenames sanitized, storage paths traversal-guarded, CSV exports escaped against formula injection,
  and containers run as non-root.
* **Background jobs:** `TaskRunner` protocol (`services/jobs.py`). The MVP uses `SyncTaskRunner` (a typical
  analysis takes about 1–2 s); an RQ or Celery runner can replace it without changes to callers.
* **Portability:** `Uuid` and JSON(B) types keep the same models working on PostgreSQL (production) and
  SQLite (tests).

## 9. Design decisions (deviations from the original brief)

1. Followers are an account time series, stored in `metric_snapshots` and lifted from exports if present.
2. Column mapping is per file, not per project.
3. Analysis output is stored as versioned JSON sections instead of dozens of relational tables.
4. Engagement uses only the components a platform reports; nothing is zero-filled.
5. Cross-platform comparison uses within-platform ratios and ranks, never raw counts.
6. Benjamini-Hochberg correction is applied across all tests in a run.
7. Timezones are explicit per project.
8. Synchronous SQLAlchemy: the workload is CPU-bound pandas.
9. AI classifications are cached per caption hash.
10. PDF comes from the HTML report (WeasyPrint in Docker, browser print elsewhere).
11. Performance-index weights are data driven by objectives, re-normalized when metrics are missing.
12. Generated numbers are verified post hoc, in addition to the prompt instructions.
