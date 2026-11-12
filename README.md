# SocialLens AI

**AI-powered multi-platform social media audit & marketing strategy agent.**

SocialLens AI takes analytics exports from **Instagram, Facebook, TikTok and LinkedIn**. It validates
and normalizes them into one schema and runs a statistical analytics engine: KPIs, format/pillar/hook/CTA
performance, timing, trends, regression, anomaly detection and cross-platform comparison. Every finding
gets a **confidence level**. An AI strategist then turns these *verified* findings into an audit, a
platform-specific strategy and a 30-day content plan, and a guardrail checks that every number the AI
writes exists in the data.

> Analytics first, AI second. The LLM never sees raw exports and never computes a metric.

* Architecture: [`docs/architecture.md`](docs/architecture.md)
* Formulas, statistics and confidence rules: [`docs/methodology.md`](docs/methodology.md)

---

## Features

| Area | What you get |
|---|---|
| Ingestion | CSV/XLSX upload (multi-file), automatic platform detection, fuzzy column mapping with confidence scores and manual correction, locale-aware parsing, validation report per file |
| Analytics | 30+ KPIs per platform (unavailable ones are marked, not zeroed), engagement/share/save/click rates, video completion, posting consistency, best and worst posts with reach thresholds, formats, content pillars, hooks and CTAs, day and time windows, weekly trends |
| Statistics | Mann-Whitney / Kruskal-Wallis with effect sizes, Spearman correlations, OLS with controls, Theil-Sen trends, robust outlier detection, Benjamini-Hochberg correction, high/medium/low confidence |
| Insights | Deterministic rule engine (content-mix imbalance, weak CTAs, posting gaps, underused winning formats, declining trends, awareness-without-traffic, …) |
| AI | Provider abstraction (Claude via Anthropic, OpenAI), structured outputs + Pydantic validation + schema-correction retry, audit / strategy / 30-day plan / content ideas / AI classification, numeric verification, request logging, versioned outputs |
| Offline mode | Without an API key, a deterministic engine produces the same audit, strategy and plan structures from the analytics |
| Demo mode | "Try demo" generates realistic synthetic exports in each platform's **native** format for 3 example businesses and runs the whole pipeline |
| Reporting | Self-contained HTML report with charts, methodology and disclaimer; print CSS; server-side PDF (WeasyPrint) in Docker |
| UI | Next.js dashboard: projects, upload and mapping, analytics (per platform + cross-platform), content analysis, audit (with impact/effort matrix), strategy, calendar, report; light/dark, mobile-friendly |

---

## Quick start (Docker)

```bash
cp .env.example .env        # optional: add ANTHROPIC_API_KEY (or OPENAI_API_KEY + AI_PROVIDER=openai)
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

Migrations run automatically when the backend starts. Open the app and click **Try demo**.

---

## Local development (without Docker)

**Backend** (Python 3.11+):

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
# PostgreSQL (recommended):
#   DATABASE_URL=postgresql+psycopg://sociallens:sociallens@localhost:5432/sociallens
# or SQLite for a quick start:
#   DATABASE_URL=sqlite:///./dev.db
alembic upgrade head
uvicorn app.main:app --reload
```

Optional server-side PDF: `pip install -r requirements-pdf.txt` (needs Pango/HarfBuzz system libraries;
already included in the Docker image). Otherwise use the report's **Print / Save as PDF** button.

**Frontend** (Node 20+):

```bash
cd frontend
npm install
npm run dev                         # http://localhost:3000, talks to NEXT_PUBLIC_API_URL (default :8000)
```

---

## Configuration

All configuration comes from environment variables (see [`.env.example`](.env.example)). Never commit `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | local PostgreSQL | SQLAlchemy URL |
| `AI_PROVIDER` | `anthropic` | `anthropic` \| `openai` \| `none` |
| `ANTHROPIC_API_KEY` | – | Enables Claude |
| `ANTHROPIC_MODEL` | `claude-opus-5` | Claude model |
| `ANTHROPIC_FALLBACKS` | `true` | Server-side refusal fallbacks (re-runs a classifier-declined request on the recommended model) |
| `AI_EFFORT` | `high` | Claude reasoning effort (`low` … `max`) |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | – / `gpt-5` | OpenAI provider |
| `MAX_UPLOAD_MB` | `20` | Upload size limit |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed origins (comma-separated) |
| `LOG_LEVEL` / `LOG_JSON` | `INFO` / `true` | Structured logging |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL used by the browser |

**AI provider setup.** Set `ANTHROPIC_API_KEY` (or `AI_PROVIDER=openai` + `OPENAI_API_KEY`) and restart
the backend. The header badge switches from "Analytics only" to the provider name. Without a key,
everything still works: audit, strategy and plan come from the rule-based engine and are labelled as such.

---

## Using the app

1. **New project**: business details, objectives (the first one is primary), platforms and timezone.
2. **Data**: drag and drop exports (Meta Business Suite for Instagram/Facebook, TikTok Studio, LinkedIn
   page exports; other layouts work too). No exports? Use *Download synthetic sample files* or the files
   in [`data/sample/`](data/sample).
3. **Mapping**: review each file's auto-detected columns (confidence and review flags), fix any mapping,
   then confirm.
4. **Import & run analysis**: creates analysis v1. Re-running creates v2 and keeps v1.
5. **Analytics / Content**: explore KPIs, charts, statistical findings and the posts table.
6. **Audit → Strategy → 30-day plan**: optional custom instructions (e.g. *"Do not recommend paid
   advertising"*). Every item shows evidence, confidence, impact and effort.
7. **Report**: open, download HTML, or export PDF.

### Demo mode

`POST /demo/generate` (or **Try demo** in the UI) creates a project for one of three businesses:

| Key | Business | Platforms / posts (90 days) | Planted patterns |
|---|---|---|---|
| `agency_uae` | Falcon Growth Studio: digital marketing agency, Dubai, lead generation | IG 100, FB 80, TikTok 75, LinkedIn 50 | Reels reach, educational saves, LinkedIn case studies, TikTok behind-the-scenes completion, promo-heavy Facebook with a posting gap |
| `cafe_paris` | Maison Mouture: specialty coffee, Paris, store visits | IG 48, TikTok 22, FB 20 | Sparse, inconsistent posting (small-sample behaviour) |
| `saas_uk` | Ledgerly: B2B SaaS, UK, website traffic | LinkedIn 52, IG 26 | Documents on LinkedIn, weekday effects |

Synthetic data is reproducible (seeded) and deliberately noisy, so patterns only emerge statistically.
CLI: `python -m app.synthetic.cli --business agency_uae --days 90 --seed 42 --out ../data/sample`.

---

## Testing & quality

```bash
cd backend  && pytest && ruff check . && ruff format --check .
cd frontend && npm test && npm run lint && npx tsc --noEmit && npm run build
```

* **Backend (pytest):** parsers, readers (UTF-16, semicolons, XLSX header detection), platform detection,
  mapping, normalization and validation, KPI math and division-by-zero, engine robustness on sparse data,
  statistics (MWU, BH, OLS recovery), confidence rules, scoring, trends, CSV injection, the full API flow,
  demo end-to-end, AI retry and guardrails with a fake provider, and the report. Tests use SQLite and
  temp storage, so no Docker is needed.
* **Frontend (Vitest + Testing Library):** formatting, API error handling, findings list, impact/effort
  matrix, dropzone.

---

## Project structure

```
backend/   FastAPI app (ingestion, analytics, ai, services, reporting, synthetic) + Alembic + tests
frontend/  Next.js app (App Router), shadcn/ui components, Recharts charts
data/      sample/ synthetic native-format exports
docs/      architecture.md, methodology.md
```

## Roadmap hooks

* **Direct API integrations**: `backend/app/integrations/` defines `SocialDataSource` for the Meta Graph,
  TikTok and LinkedIn APIs. Sources feed the same ingestion path. Status: `GET /meta/integrations`.
* **Multimodal analysis**: posts store `thumbnail_url`, `media_url` and `visual_features`;
  `analytics/visual.py` defines the extractor interface.
* **Background jobs**: swap `SyncTaskRunner` for an RQ or Celery runner (`services/jobs.py`).
* **Auth / multi-tenancy**: `users` table and `projects.owner_id` are in place.

---

*Recommendations are based on available historical data and should be tested and adjusted over time.*
