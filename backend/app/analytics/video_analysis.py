"""Video performance: duration vs completion and reach."""

import pandas as pd

from app.analytics.common import MIN_GROUP_SIZE, disp, fnum, pct_diff, platform_label
from app.analytics.findings import Finding
from app.analytics.grouping import group_table
from app.analytics.statistics import mann_whitney, spearman

DURATION_BUCKETS = [(0, 15, "0-15s"), (15, 30, "16-30s"), (30, 60, "31-60s"), (60, 120, "61-120s"), (120, 1e9, "120s+")]
SHORT_MAX = 30


def bucket(seconds: float) -> str | None:
    if pd.isna(seconds):
        return None
    return next(lbl for lo, hi, lbl in DURATION_BUCKETS if lo < seconds <= hi or (lo == 0 and seconds == 0))


def analyze_video(g: pd.DataFrame, platform: str, exposure_metric: str | None) -> tuple[dict, list[Finding]]:
    videos = g[g["is_video"]]
    out: dict = {"video_count": int(len(videos))}
    if len(videos) < MIN_GROUP_SIZE:
        out["note"] = "Too few videos for video analysis."
        return out, []
    out["median_completion"] = fnum(videos["completion"].median(), 1)
    out["median_duration_seconds"] = fnum(videos["video_duration_seconds"].median(), 1)
    out["median_avg_watch_seconds"] = fnum(videos["average_watch_time_seconds"].median(), 1)
    out["video_share_of_posts"] = fnum(len(videos) / len(g) * 100, 1)
    non_video = g[~g["is_video"]]
    if len(non_video) >= MIN_GROUP_SIZE:
        out["video_vs_static_median_exposure"] = {
            "video": fnum(videos["exposure"].median(), 0),
            "static": fnum(non_video["exposure"].median(), 0),
        }
    with_duration = videos.dropna(subset=["video_duration_seconds"])
    out["by_duration"] = group_table(
        with_duration.assign(duration_bucket=with_duration["video_duration_seconds"].map(bucket)), "duration_bucket"
    )
    order = {lbl: i for i, (_, _, lbl) in enumerate(DURATION_BUCKETS)}
    out["by_duration"].sort(key=lambda r: order.get(r["group"], 99))
    out["scatter"] = [
        {
            "duration": fnum(r.video_duration_seconds, 0),
            "completion": fnum(r.completion, 1),
            "exposure": fnum(r.exposure, 0),
        }
        for r in with_duration.itertuples()
    ]

    findings: list[Finding] = []
    where = platform_label(platform)
    for metric, name in (("completion", "completion rate"), ("exposure", exposure_metric or "reach")):
        corr = spearman(with_duration["video_duration_seconds"], with_duration[metric])
        if corr:
            direction = "longer videos tend to have lower" if corr.rho < 0 else "longer videos tend to have higher"
            findings.append(
                Finding(
                    id=f"video:{platform}:duration_vs_{metric}",
                    category="video",
                    platform=platform,
                    statement=f"On {where}, {direction} {name} (Spearman rho={corr.rho:.2f}, n={corr.n}).",
                    metric=metric,
                    values={"rho": fnum(corr.rho, 3), "n": corr.n},
                    sample_size=corr.n,
                    p_value=corr.p_value,
                    effect_size=fnum(corr.rho, 3),
                    method="Spearman rank correlation",
                )
            )
        short = with_duration.loc[with_duration["video_duration_seconds"] <= SHORT_MAX, metric]
        long_ = with_duration.loc[with_duration["video_duration_seconds"] > SHORT_MAX, metric]
        test = mann_whitney(short, long_)
        if test:
            diff = pct_diff(test.median_a, test.median_b)
            findings.append(
                Finding(
                    id=f"video:{platform}:short_vs_long_{metric}",
                    category="video",
                    platform=platform,
                    statement=(
                        f"On {where}, videos of {SHORT_MAX}s or less have a median {name} of {disp(test.median_a)} "
                        f"vs {disp(test.median_b)} for longer videos"
                        + (f" ({diff:+.1f}%)." if diff is not None else ".")
                    ),
                    metric=metric,
                    values={
                        "short_median": fnum(test.median_a, 3),
                        "long_median": fnum(test.median_b, 3),
                        "n_short": test.n_a,
                        "n_long": test.n_b,
                        "short_max_seconds": SHORT_MAX,
                    },
                    sample_size=min(test.n_a, test.n_b),
                    p_value=test.p_value,
                    effect_size=fnum(test.rank_biserial, 3),
                    difference_pct=diff,
                    method="Mann-Whitney U, rank-biserial r",
                )
            )
    return out, findings
