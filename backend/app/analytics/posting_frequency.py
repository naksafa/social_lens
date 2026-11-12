"""Posting frequency and consistency.

consistency_score (0-100) = 100 x (1 - min(CV_weekly, 1)) x gap_penalty, where
CV_weekly is the coefficient of variation of posts per calendar week (including
weeks with zero posts) and gap_penalty = 1 for a longest gap <= 7 days, then
decreases linearly to 0.5 at 28+ days.

Labels: high >= 70, moderate 45-69, low < 45. The numbers behind the label are always
reported so the judgement is never arbitrary.
"""

import pandas as pd

from app.analytics.common import fnum


def analyze_posting(g: pd.DataFrame, period: tuple[pd.Timestamp, pd.Timestamp]) -> dict:
    start, end = period
    days = max(1, (end - start).days + 1)
    times = g["local_time"].sort_values()
    dates = times.dt.normalize()

    # Weekly counts across the whole period, zero-filled.
    week_index = pd.Index(times.dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time)
    all_weeks = pd.period_range(start.tz_localize(None), end.tz_localize(None), freq="W-SUN").start_time
    counts = pd.Series(week_index).value_counts().reindex(all_weeks, fill_value=0)
    # Edge weeks are only partly inside the period; scale them to a 7-day rate so a
    # 2-day first week doesn't look like a posting drop.
    s0, e0 = start.tz_localize(None).normalize(), end.tz_localize(None).normalize()
    covered = pd.Series(
        [(min(w + pd.Timedelta(days=6), e0) - max(w, s0)).days + 1 for w in counts.index], index=counts.index
    ).clip(lower=1)
    weekly_rate = counts * 7 / covered
    weekly_mean = float(weekly_rate.mean()) if len(weekly_rate) else 0.0
    cv = float(weekly_rate.std(ddof=0) / weekly_mean) if weekly_mean > 0 else 1.0

    # "Gap" = consecutive calendar days without any post (Jan 10 -> Jan 26 is a 15-day gap).
    gaps = dates.diff().dt.days.dropna()
    idle = (gaps - 1).clip(lower=0)
    lead_gap = (dates.iloc[0] - start.normalize()).days if len(dates) else days
    tail_gap = (end.normalize() - dates.iloc[-1]).days if len(dates) else days
    longest_gap = int(max([0, *idle.tolist(), lead_gap, tail_gap]))
    gap_penalty = 1.0 if longest_gap <= 7 else max(0.5, 1 - (longest_gap - 7) / 42)
    score = 100 * (1 - min(cv, 1.0)) * gap_penalty
    label = "high" if score >= 70 else "moderate" if score >= 45 else "low"

    inactivity = []
    prev = start.normalize()
    for d in [*dates.drop_duplicates().tolist(), end.normalize() + pd.Timedelta(days=1)]:
        gap = (d - prev).days - 1
        if gap >= 7:
            inactivity.append({"from": (prev + pd.Timedelta(days=1)).date().isoformat(), "days": int(gap)})
        prev = d

    return {
        "posts": int(len(g)),
        "period_days": days,
        "posts_per_week": fnum(len(g) / days * 7, 2),
        "posts_per_month": fnum(len(g) / days * 30.44, 1),
        "active_days": int(dates.nunique()),
        "active_weeks_pct": fnum((counts > 0).mean() * 100, 1),
        "weekly_counts": [{"week": w.date().isoformat(), "posts": int(c)} for w, c in counts.items()],
        "weekly_cv": fnum(cv, 3),
        "median_days_between_posts": fnum(gaps.median(), 2) if len(gaps) else None,
        "mean_days_between_posts": fnum(gaps.mean(), 2) if len(gaps) else None,
        "longest_gap_days": longest_gap,
        "inactivity_periods": inactivity,
        "consistency_score": fnum(score, 1),
        "consistency": label,
        "method": "score = 100*(1-min(CV_weekly,1))*gap_penalty; gap_penalty falls from 1 (<=7d) to 0.5 (>=28d)",
    }
