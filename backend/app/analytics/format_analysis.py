"""Content format analysis (Reels vs carousels vs images, documents vs text...)."""

import pandas as pd

from app.analytics.common import format_label
from app.analytics.findings import Finding
from app.analytics.grouping import compare_groups, group_table


def analyze_formats(g: pd.DataFrame, platform: str, exposure_metric: str | None) -> tuple[dict, list[Finding]]:
    table = group_table(g, "content_format")
    for row in table:
        row["label"] = format_label(row["group"])
    findings: list[Finding] = []
    metrics = ["exposure", "er", "share_rate", "save_rate", "performance_index"]
    for metric in metrics:
        if metric in g and g[metric].notna().sum() >= 10:
            findings += compare_groups(
                g, "content_format", metric,
                platform=platform, category="format", exposure_metric=exposure_metric,
                group_label=format_label,
            )  # fmt: skip
    return {"formats": table, "format_count": len(table)}, findings
