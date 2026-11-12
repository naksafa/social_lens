# SocialLens AI — Analytical Methodology

Everything described here is computed deterministically in Python (`backend/app/analytics/`)
**before** any AI model is involved. The AI layer receives these results and interprets them; it
cannot add metrics of its own (see [AI grounding](#9-ai-grounding-and-verification)).

---

## 1. Data preparation

| Step | What happens | Code |
|---|---|---|
| Reading | CSV (encoding + delimiter sniffing: UTF‑8/UTF‑16/cp1252; `, ; \t \|`) and XLSX (the sheet with the most data is chosen). Description rows above the header are skipped automatically. | `ingestion/readers.py` |
| Platform detection | Column-name signatures, typical cell values (e.g. "IG reel", "Sponsored") and filename hints are scored per platform. Confidence mixes the best platform's share of the evidence with its margin over the runner-up. | `ingestion/platform_detection.py` |
| Column mapping | For each column/field pair: an exact platform alias scores 1.00, an exact generic alias 0.95, and otherwise fuzzy similarity (rapidfuzz: token-set + ratio) is used, heavily discounted below 0.8 similarity. The score is multiplied by a **type-compatibility factor** from the column profile (numeric ratio, date ratio, uniqueness for IDs). Assignment is greedy and one-to-one. Scores < 0.60 are left unmapped; scores < 0.85 are flagged for review. | `ingestion/mapping.py` |
| Parsing | Localized numbers (`1,234`, `1.234,5`, `1.2K`, `(12)`, `12%`), column-level EU thousands detection (`4.210`), durations (`0:45`, `1m 5s`, header units like `(h)`), percentages (fractions → %), dates (day-first detection, Excel serials, UTC offsets) in the project timezone. | `ingestion/parsers.py` |
| Validation | Missing required fields, unreadable dates, non-numeric values, negative metrics, impossible percentages, reach > impressions, duplicate posts, empty rows, suspicious outliers (robust z > 10 on log scale). Bad values are nulled and reported; only unusable datasets are rejected. | `ingestion/validation.py`, `ingestion/normalizer.py` |

Account-level metrics (followers) are stored separately as daily `MetricSnapshot`s.

---

## 2. Derived metrics (feature engineering)

All rates are percentages. **Any zero or missing denominator gives "not available", never an error or ∞.**

| Metric | Formula |
|---|---|
| Engagement | `likes + comments + shares + saves`, using only components the platform reports (saves are excluded on LinkedIn/Facebook rather than counted as 0) |
| Exposure | Platform's primary reach-type metric: Instagram/Facebook → **reach**, TikTok → **views**, LinkedIn → **impressions** (fallbacks in `EXPOSURE_PRIORITY`) |
| Engagement rate (ER) | `engagement / exposure × 100` |
| ER by reach / impressions / views / followers | `engagement / <denominator> × 100` (each when available) |
| Share rate, save rate, comment rate | `component / exposure × 100` |
| CTR | `clicks / impressions × 100` (falls back to exposure if impressions are missing) |
| Click rate | `clicks / exposure × 100` |
| Video completion | native completion rate, else `average watch time / video duration × 100` |
| Follower conversion | `followers gained / exposure × 100` |
| Posting interval | days between consecutive posts per platform |
| Content features | caption length, hashtag count, CTA present, opening hook type, video flag, local day/hour, weekday/weekend |

**Aggregate vs. median.** KPIs report both aggregate rates (ratio of sums, e.g. total engagement / total
reach, which weights big posts more) and median per-post rates (robust to viral outliers).

---

## 3. Content classification

A transparent keyword classifier assigns each caption a **topic** (educational, promotional, product,
service, behind the scenes, testimonial, entertainment, trend, company culture, case study, tips, FAQ,
community, announcement, other), a **pillar** (educational, promotional, social proof, entertainment,
brand, community), a **CTA type**, and a **hook type** (question, number, POV, how-to, bold claim).
Confidence is `top score / (top + runner-up)`, damped for weak evidence.

Low-confidence posts can optionally be re-classified by the LLM (`POST /projects/{id}/classify`).
Results are cached by `(caption hash, taxonomy version, model)`, so no caption is ever classified twice.
Labels provided in the upload are never overwritten.

---

## 4. Statistical methods

Social metrics are right-skewed with viral outliers, so the engine uses **rank-based, non-parametric
methods and medians**.

| Question | Method | Effect size |
|---|---|---|
| Is group A different from group B (e.g. Reels vs Images)? | Mann-Whitney U (two-sided) | rank-biserial *r* (0.1 small, 0.3 medium, 0.5 large) |
| Do 3+ groups differ (formats, pillars)? | Kruskal-Wallis H | ε² = H/(n−1) (0.01 / 0.08 / 0.26) |
| Is there a monotone relationship (video length vs completion)? | Spearman ρ | ρ |
| What is each factor's effect *holding others constant*? | OLS on `log(1 + exposure)` with dummies for format, pillar, hook and weekend (rare levels merged into the baseline) | % effect = `exp(β) − 1`, with SE, p-value, R² |
| Is a metric trending? | Theil-Sen slope on weekly medians plus a Spearman test of week vs. value | % change over the period |
| Which posts are outliers? | Robust z-score (median/MAD) > 3 on log exposure and on ER; IQR fences also reported | — |

**Guards.** Groups need ≥ 5 posts to be reported and ≥ 8 per group to be tested. Trends need ≥ 4
complete weeks, and partial edge weeks are shown but not fitted.

**Multiple testing.** One analysis runs dozens of tests (formats × pillars × days × platforms). All
p-values in a run are adjusted together with **Benjamini-Hochberg** (FDR α = 0.05) before confidence is
assigned. Without this, several "significant" findings per run would be false positives.

**Trend labels.** *Growth/decline* means Spearman p < 0.10 and |total change| ≥ 10%. Otherwise the series is
*volatile* if its coefficient of variation is > 0.5, and *plateau* if not.

---

## 5. Confidence system

Every finding is graded **high / medium / low** by explicit rules (`analytics/confidence.py`):

1. **Sample size ceiling:** n ≥ 30 → high, 10–29 → medium, < 10 → low (n = the smallest group compared).
2. **Significance:** adjusted p ≥ 0.20 caps at low; 0.05 ≤ p < 0.20 downgrades one level.
3. **Effect size:** a negligible effect (|r| < 0.1 or |difference| < 10%) downgrades one level.
4. **Completeness:** < 70% non-missing values downgrades one level.

The reasons are stored with the finding and shown in the UI (hover "method").

---

## 6. Robust best/worst content

Rate-based rankings (engagement rate, completion) only include posts whose exposure is at least
`max(100, 25th percentile of the platform)`. A post seen by 40 people with 10 likes (25% ER) is
therefore never crowned the "best" post. Rankings exist for reach, engagement, ER, saves, shares, clicks,
video views, completion, the performance index, and the bottom performers.

---

## 7. Performance index

```
performance_index(post) = Σ wᵢ · pct_rankᵢ(post) / Σ wᵢ      (over metrics present for the post)
```

* `pct_rankᵢ` is the post's percentile rank (0–100) for metric *i* **within its own platform**, so the
  index is scale-free.
* Weights come from the **ObjectiveWeightingService** (`analytics/scoring.py`) based on the business's
  marketing objectives. Examples:

| Objective | Highest weights |
|---|---|
| Brand awareness | exposure 0.45, share rate 0.20, ER 0.15 |
| Engagement | ER 0.35, comment/share/save rates 0.20 each |
| Lead generation | leads 0.30, click rate 0.30, … |
| Website traffic | click rate 0.45, exposure 0.25 |
| Video views | exposure 0.40, completion 0.35 |

* With several objectives, weights are summed and the **primary (first) objective counts double**.
* Metrics a platform does not report are dropped and the remaining weights re-normalized. LinkedIn is not
  penalised for having no saves.
* Weights can be overridden per run (`POST /analyze {"weight_overrides": …}`). The weights used are
  stored with every run.

---

## 8. Posting consistency and cross-platform comparison

**Consistency score** (0–100):

```
score = 100 × (1 − min(CV_weekly, 1)) × gap_penalty
```

`CV_weekly` is the coefficient of variation of posts per calendar week (zero-filled, with partial edge
weeks scaled to a 7-day rate). `gap_penalty` is 1 for a longest gap ≤ 7 days, falling linearly to 0.5 at
≥ 28 days. Labels: high ≥ 70, moderate 45–69, low < 45. A "gap" means consecutive calendar days
without any post.

**Why cross-platform comparison needs normalization.** Platforms count exposure differently: Instagram
*reach* counts unique accounts, TikTok *views* counts plays (including repeats and non-followers), and
LinkedIn *impressions* counts feed renders. Comparing "15,000 TikTok views" with "3,000 LinkedIn
impressions" would be meaningless. The cross-platform module therefore compares only:

* unitless ratios within each platform's own exposure definition (median ER, clicks per 1k exposure,
  follows per 1k exposure);
* process metrics that share a unit (posts per week, consistency score);
* each platform's trend relative to itself;
* rank positions across platforms (0–100 scores per dimension).

"Underutilized" means the platform ranks high on efficiency (mean percentile of ER, click and follow
rates) but receives a low share of posting effort.

---

## 9. AI grounding and verification

* The LLM receives a compact **analytics summary**: KPIs, format/pillar tables, timing, trends, top and
  bottom posts, high and medium-confidence findings (with n, adjusted p, effect size), rule-based
  insights and data limitations. It never receives raw exports.
* System prompts require every factual claim to come from the supplied analytics, cite finding/insight
  IDs, state uncertainty for weak evidence, say "Insufficient data to determine this" when data is
  missing, and label each recommendation as *data-backed* or *general best practice*.
* Outputs use **structured outputs** validated by Pydantic. On a schema violation the call is retried
  once with the validation error ("schema correction").
* **Numeric verification.** After generation, every number in evidence, explanation and summary fields
  is matched against the numbers in the analytics payload **at the precision it was written**
  (`guardrails.py`). Unmatched numbers are reported as "to review" in the UI and the report. Small
  integers (≤ 31) and years are exempt, because they are usually prescriptive ("post 3 times a week").
* Without an API key, a deterministic composer builds the audit, strategy and plan from the same insights
  and analytics. It is clearly labelled "Rule-based engine".

---

## 10. Limitations

* Findings are **correlational**. Timing and content effects may be confounded by topic, seasonality or
  paid boosts. The regression model reduces, but does not remove, this.
* Exports contain no demographics, so audience insights describe interaction behaviour only.
* Small accounts produce small samples. The confidence system is designed to say so rather than overstate.
* The synthetic demo data has planted, noisy patterns; it demonstrates the pipeline, not real benchmarks.

> Recommendations are based on available historical data and should be tested and adjusted over time.
