"""Loading canonical posts from the database into pandas."""

import uuid

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SocialPost

_COLUMNS = [c.key for c in SocialPost.__table__.columns if c.key not in ("created_at", "updated_at", "extra")]


def load_posts_frame(db: Session, project_id: uuid.UUID, platform: str | None = None) -> pd.DataFrame:
    stmt = select(*[SocialPost.__table__.c[c] for c in _COLUMNS]).where(SocialPost.project_id == project_id)
    if platform:
        stmt = stmt.where(SocialPost.platform == platform)
    rows = db.execute(stmt).mappings().all()
    df = pd.DataFrame([dict(r) for r in rows], columns=_COLUMNS)
    if df.empty:
        return df
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True)
    for col in ("platform", "topic_source"):
        df[col] = df[col].map(lambda v: getattr(v, "value", v))
    return df
