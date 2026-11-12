"""Write canonical synthetic data in each platform's *native* export format.

Demo data then flows through the real ingestion path (detection, fuzzy mapping,
locale parsing, validation) instead of bypassing it.
"""

import io

import numpy as np
import pandas as pd

from app.core.enums import Platform

_IG_TYPES = {"reel": "IG reel", "carousel": "IG carousel", "image": "IG image"}
_FB_TYPES = {"image": "Photos", "video": "Videos", "link": "Links", "text": "Status", "reel": "Reels"}
_LI_TYPES = {"text": "Text", "image": "Image", "document": "Document", "video": "Video"}


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None or pd.isna(seconds):
        return ""
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def _blank(v: object) -> object:
    """Missing -> empty cell; whole-number floats -> ints (exports show counts as integers)."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def to_instagram(df: pd.DataFrame, handle: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Post ID": df["external_post_id"].str.replace("in", "1790", regex=False),
            "Account username": handle,
            "Description": df["caption"],
            "Duration (sec)": df["video_duration_seconds"].map(lambda v: "" if pd.isna(v) else int(v)),
            "Publish time": df["published_at"].map(lambda t: t.strftime("%m/%d/%Y %H:%M")),
            "Permalink": "https://www.instagram.com/p/" + df["external_post_id"],
            "Post type": df["content_format"].map(_IG_TYPES),
            "Views": df["views"].map(_blank),
            "Reach": df["reach"].map(_blank),
            "Impressions": df["impressions"].map(_blank),
            "Likes": df["likes"],
            "Shares": df["shares"],
            "Follows": df["followers_gained"],
            "Comments": df["comments"],
            "Saves": df["saves"],
            "Profile visits": df["profile_visits"],
            "Website taps": df["clicks"],
        }
    )


def to_facebook(df: pd.DataFrame, page_name: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Post ID": "fb_" + df["external_post_id"],
            "Page name": page_name,
            "Title": "",
            "Description": df["caption"],
            "Duration (sec)": df["video_duration_seconds"].map(lambda v: "" if pd.isna(v) else int(v)),
            "Publish time": df["published_at"].map(lambda t: t.strftime("%m/%d/%Y %H:%M")),
            "Permalink": "https://www.facebook.com/" + df["external_post_id"],
            "Post type": df["content_format"].map(_FB_TYPES),
            "Reach": df["reach"].map(_blank),
            "Impressions": df["impressions"].map(_blank),
            "Reactions": df["likes"],
            "Comments": df["comments"],
            "Shares": df["shares"],
            "Total clicks": df["clicks"],
            "3-second video views": df["views"].map(_blank),
        }
    )


def to_tiktok(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Video title": df["caption"],
            "Video link": "https://www.tiktok.com/@demo/video/" + df["external_post_id"],
            "Post time": df["published_at"].map(lambda t: t.strftime("%Y-%m-%d %H:%M")),
            "Total likes": df["likes"],
            "Total comments": df["comments"],
            "Total shares": df["shares"],
            "Add to Favorites": df["saves"],
            "Video views": df["views"].map(_blank),
            "Total play time (h)": (df["watch_time_seconds"] / 3600).round(2),
            "Average watch time": df["average_watch_time_seconds"],
            "Watched full video": df["completion_rate"].map(lambda v: f"{v:.1f}%"),
            "Reached audience": df["reach"].map(_blank),
            "New followers": df["followers_gained"],
            "Profile views": df["profile_visits"],
            "Video duration": df["video_duration_seconds"].map(_fmt_duration),
        }
    )


def to_linkedin(df: pd.DataFrame, company: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Update title": df["caption"],
            "Update link": "https://www.linkedin.com/feed/update/urn:li:activity:" + df["external_post_id"],
            "Update type": df["paid_or_organic"].map({"paid": "Sponsored", "organic": "Organic"}),
            "Content type": df["content_format"].map(_LI_TYPES),
            "Posted by": company,
            "Created date": df["published_at"].map(lambda t: t.strftime("%m/%d/%Y")),
            "Impressions": df["impressions"].map(_blank),
            "Views (excluding off-site video views)": df["views"].map(_blank),
            "Clicks": df["clicks"],
            "Reactions": df["likes"],
            "Comments": df["comments"],
            "Reposts": df["shares"],
            "Follows": df["followers_gained"],
        }
    )


def native_export(df: pd.DataFrame, platform: Platform, account_name: str, handle: str) -> tuple[str, bytes]:
    """Return (filename, file bytes) in the platform's native export format."""
    if platform == Platform.INSTAGRAM:
        return f"instagram_{handle}_posts.csv", to_instagram(df, handle).to_csv(index=False).encode("utf-8-sig")
    if platform == Platform.FACEBOOK:
        return f"facebook_{handle}_posts.csv", to_facebook(df, account_name).to_csv(index=False).encode("utf-8-sig")
    if platform == Platform.TIKTOK:
        return f"tiktok_{handle}_videos.csv", to_tiktok(df).to_csv(index=False).encode("utf-8")
    # LinkedIn page exports are XLSX with a title row above the header.
    body = to_linkedin(df, account_name)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame([["Metric", "Value"], ["Total updates", len(body)]]).to_excel(
            writer, sheet_name="Metrics", header=False, index=False
        )
        title = pd.DataFrame([[f"All posts - {account_name} (exported)"] + [None] * (body.shape[1] - 1)])
        title.to_excel(writer, sheet_name="All posts", header=False, index=False)
        body.to_excel(writer, sheet_name="All posts", index=False, startrow=1)
    return f"linkedin_{handle}_updates.xlsx", buf.getvalue()


def inject_quality_issues(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Add a few realistic defects (a duplicated row, blank metric) to exercise validation."""
    if len(df) < 10:
        return df
    out = pd.concat([df, df.iloc[[int(rng.integers(0, len(df)))]]], ignore_index=True)
    metric = "reach" if "reach" in out and out["reach"].notna().any() else "impressions"
    out.loc[int(rng.integers(0, len(out))), metric] = None
    return out
