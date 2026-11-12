"""Small hand-written exports mimicking real platform formats."""

import io

import pandas as pd

INSTAGRAM_CSV = """Post ID,Account username,Description,Duration (sec),Publish time,Permalink,Post type,Views,Reach,Likes,Shares,Follows,Comments,Saves
1790001,acme,"3 mistakes to avoid when hiring an agency #marketing #tips",32,09/03/2025 18:05,https://instagram.com/p/1,IG reel,15230,12400,540,88,12,31,120
1790002,acme,"Our new service package is live - book a call today! #offer",,09/05/2025 12:00,https://instagram.com/p/2,IG image,,3100,95,2,1,4,3
1790003,acme,"Behind the scenes of our shoot",,09/07/2025 20:30,https://instagram.com/p/3,IG carousel,,6200,310,14,3,12,85
1790004,acme,"How we grew a client 3x (case study)",45,09/10/2025 17:45,https://instagram.com/p/4,IG reel,22010,18950,910,160,25,44,300
1790004,acme,"How we grew a client 3x (case study)",45,09/10/2025 17:45,https://instagram.com/p/4,IG reel,22010,18950,910,160,25,44,300
1790005,acme,"Weekend vibes",,not a date,https://instagram.com/p/5,IG image,,1500,40,0,0,1,0
1790006,acme,"FAQ: how long does SEO take?",,09/14/2025 09:10,https://instagram.com/p/6,IG carousel,,5400,-5,6,2,9,70
"""

# Semicolon delimiter + European decimal/thousand formats, as in EU locale exports.
FACEBOOK_CSV = """Post ID;Page name;Title;Publish time;Post type;Reach;Reactions;Comments;Shares;Total clicks
fb_1;Acme;Spring offer - 20% off;2025-09-02 10:00;Photos;4.210;120;8;5;96
fb_2;Acme;Team day out;2025-09-04 15:30;Videos;6.800;340;22;41;60
fb_3;Acme;Read our latest guide;2025-09-09 11:15;Links;2.150;35;2;1;210
fb_4;Acme;We are hiring!;2025-09-12 09:00;Status;1.980;60;11;3;25
"""

TIKTOK_CSV = """Video title,Video link,Post time,Total likes,Total comments,Total shares,Add to Favorites,Video views,Total play time (h),Average watch time,Watched full video,Reached audience,New followers,Video duration
POV: your first agency meeting,https://tiktok.com/v/1,2025-09-01 19:00,2300,120,410,150,48000,110.5,8.3,31.2%,39000,210,0:22
Behind the scenes edit,https://tiktok.com/v/2,2025-09-03 21:00,1800,80,120,60,30500,70.0,8.9,44.0%,26000,90,0:15
Why your ads fail (explained),https://tiktok.com/v/3,2025-09-06 18:30,900,70,60,200,15200,62.3,14.7,12.5%,13100,40,1:35
"""


def linkedin_xlsx() -> bytes:
    """LinkedIn page exports put a description row above the real header."""
    rows = [
        ["All posts - Acme page updates, Sep 2025", None, None, None, None, None, None, None, None],
        [
            "Update title",
            "Update link",
            "Update type",
            "Created date",
            "Impressions",
            "Clicks",
            "Reactions",
            "Comments",
            "Reposts",
        ],
        ["Case study: 3x leads for a clinic", "https://lnkd.in/1", "Organic", "09/02/2025", 5400, 180, 140, 22, 12],
        ["We are hiring a strategist", "https://lnkd.in/2", "Organic", "09/05/2025", 3100, 45, 90, 14, 6],
        ["Webinar: B2B lead gen", "https://lnkd.in/3", "Sponsored", "09/11/2025", 12100, 460, 95, 8, 4],
    ]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame([["Summary", 1]]).to_excel(w, sheet_name="Metrics", header=False, index=False)
        pd.DataFrame(rows).to_excel(w, sheet_name="All posts", header=False, index=False)
    return buf.getvalue()
