"""Reproduce code-review findings without touching the application's dev database.

Run with backend/.venv/Scripts/python.exe review/diagnostics.py from the repo root.
Uses an isolated temporary SQLite database, synthetic data, and no external AI calls.
Assertions document the observed bugs, not the intended product behavior.
"""

import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TEMP = Path(tempfile.mkdtemp(prefix="sociallens-review-"))
os.environ.update(
    ENVIRONMENT="test",
    DATABASE_URL=f"sqlite:///{(TEMP / 'review.db').as_posix()}",
    STORAGE_LOCAL_PATH=str(TEMP / "storage"),
    AI_PROVIDER="none",
    LOG_LEVEL="CRITICAL",
)
sys.path.insert(0, str(ROOT / "backend"))

import pandas as pd
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import select

from app.ai.guardrails import verify_output
from app.analytics.features import engineer_features
from app.analytics.findings import FindingCollector, benjamini_hochberg
from app.analytics.kpi_engine import platform_kpis
from app.analytics.statistical_models import analyze_statistics
from app.analytics.statistics import OLSResult, OLSTerm
from app.core.enums import ClassificationSource, Platform
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.ingestion.normalizer import normalize_table
from app.ingestion.parsers import parse_datetime_series
from app.ingestion.readers import read_table
from app.main import app
from app.models import SocialPost
from app.reporting.report_service import ReportService
from app.services.project_service import ProjectService
from tests.test_api_ingestion import PROJECT

logging.disable(logging.CRITICAL)
Base.metadata.create_all(engine)
results = {}


def project(client, name="Review fixture"):
    response = client.post("/projects", json={**PROJECT, "name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


CSV = b"Post ID,Publish time,Description,Likes,Reach\np1,2026-09-01 12:00,hello,10,100\np2,2026-09-02 12:00,world,20,200\n"


def upload_and_map(client, pid):
    response = client.post(f"/projects/{pid}/files", files={"files": ("instagram.csv", CSV, "text/csv")})
    assert response.status_code == 201, response.text
    f = response.json()[0]
    mapping = [{"source_column": m["source_column"], "target_field": m["target_field"]} for m in f["mappings"]]
    response = client.post(f"/projects/{pid}/files/{f['id']}/mapping/confirm", json={"platform": "instagram", "mappings": mapping})
    assert response.status_code == 200, response.text
    return f, mapping


raw = pd.DataFrame({"date": ["2026-09-01", "2026-09-02"], "completion": ["0.5%", "1%"]})
normalized = normalize_table(raw, {"date": "published_at", "completion": "completion_rate"}, Platform.TIKTOK)
results["explicit_percent_inflated"] = normalized.posts.completion_rate.tolist()
assert results["explicit_percent_inflated"] == [50.0, 100.0]

posts = pd.DataFrame({"platform": ["instagram", "instagram"], "published_at": pd.to_datetime(["2026-09-01", "2026-09-02"], utc=True), "reach": [100.0, 100.0]})
features, infos = engineer_features(posts)
features["performance_index"] = float("nan")
kpis = platform_kpis(features, infos["instagram"])
results["missing_engagement_reported_as_zero"] = {"engagement_rate": kpis["metrics"]["engagement_rate"], "total_engagement": kpis["unavailable"].get("total_engagement")}
assert kpis["metrics"]["engagement_rate"] == 0

mixed, _ = parse_datetime_series(pd.Series(["2026-09-01 12:00:00+04:00", "2026-09-02 12:00:00"]), "Asia/Dubai")
results["mixed_timezone_naive_row"] = {"actual_utc": mixed.iloc[1].isoformat(), "expected_utc": "2026-09-02T08:00:00+00:00"}
assert mixed.iloc[1].hour == 12

table = read_table(b"Post ID,Publish time,Likes\np1,2026-09-01,10\np2,2026-09-02,20,unexpected\np3,2026-09-03,30\n", ".csv")
results["malformed_csv_silently_dropped"] = {"source_data_rows": 3, "parsed_rows": len(table.df)}
assert len(table.df) == 2

class Output(BaseModel):
    summary: str

results["unsupported_small_stat_verified"] = verify_output(Output(summary="Engagement rate is 25%."), {"engagement_rate": 1.3})
assert results["unsupported_small_stat_verified"]["status"] == "verified"

reg = OLSResult("exposure", 100, 0.4, 0.3, [OLSTerm("content_format=reel", 0.4, 49.2, 0.1, 0.04)] + [OLSTerm(f"hook_type=level{i}", 0.1, 10.5, 0.1, 0.6) for i in range(9)], {"content_format": "image"})
stats_frame = pd.DataFrame({"has_time": [True], "is_weekend": [False], "caption_length": [1], "hashtag_count": [0], "hour": [12], "er": [1], "exposure": [100]})
with patch("app.analytics.statistical_models.spearman", return_value=None), patch("app.analytics.statistical_models.ols_log_target", return_value=reg):
    _, findings = analyze_statistics(stats_frame, "instagram", "reach")
collector = FindingCollector()
collector.extend(findings)
adjusted = collector.finalize()[0]
results["fdr_preselection"] = {"tested_terms": 10, "terms_sent_to_correction": len(findings), "reported_adjusted_p": adjusted.p_adjusted, "all_terms_adjusted_p": benjamini_hochberg([0.04] + [0.6] * 9)[0]}
assert adjusted.significant and results["fdr_preselection"]["all_terms_adjusted_p"] > 0.05

with TestClient(app, raise_server_exceptions=False) as client:
    pid = project(client)
    f, mapping = upload_and_map(client, pid)
    first = client.post(f"/projects/{pid}/normalize").json()
    assert first["total_posts"] == 2
    with SessionLocal() as db:
        post = db.scalars(select(SocialPost).where(SocialPost.project_id == uuid.UUID(pid))).first()
        post.topic_source = ClassificationSource.AI
        post.content_topic = "educational"
        post.content_pillar = "educational"
        old_id = str(post.id)
        db.commit()
    client.post(f"/projects/{pid}/normalize")
    with SessionLocal() as db:
        post = db.scalars(select(SocialPost).where(SocialPost.project_id == uuid.UUID(pid), SocialPost.external_post_id == "p1")).first()
        results["reimport_erases_ai_classification"] = {"before_source": "ai", "after_source": post.topic_source, "id_changed": str(post.id) != old_id}
        assert post.topic_source is None

    bad_mapping = [{**m, "target_field": ("published_at" if m["source_column"] == "Description" else None if m["target_field"] == "published_at" else m["target_field"])} for m in mapping]
    confirm = client.post(f"/projects/{pid}/files/{f['id']}/mapping/confirm", json={"platform": "instagram", "mappings": bad_mapping})
    assert confirm.status_code == 200
    failure = client.post(f"/projects/{pid}/normalize").json()
    results["failed_reimport_deletes_existing_posts"] = {"before": 2, "after": failure["total_posts"], "file_status": failure["files"][0]["status"]}
    assert failure["total_posts"] == 0

    batch_pid = project(client, "Batch upload")
    batch = client.post(f"/projects/{batch_pid}/files", files=[("files", ("valid.csv", CSV, "text/csv")), ("files", ("invalid.exe", b"invalid", "application/octet-stream"))])
    batch_files = client.get(f"/projects/{batch_pid}/files").json()
    results["failed_batch_upload_partially_commits"] = {"http_status": batch.status_code, "files_saved": len(batch_files)}
    assert batch.status_code == 415 and len(batch_files) == 1

    unicode_pid = project(client, "\u0645\u0634\u0631\u0648\u0639")
    csv_export = client.get(f"/projects/{unicode_pid}/export/posts.csv")
    results["unicode_csv_export"] = {"http_status": csv_export.status_code}
    assert csv_export.status_code == 500

    null_update = client.put(f"/projects/{unicode_pid}", json={"name": None})
    results["nullable_update_vs_database"] = {"http_status": null_update.status_code}
    assert null_update.status_code == 500

    demo = client.post("/demo/generate", json={"business": "cafe_paris", "days": 30, "seed": 7})
    assert demo.status_code == 201, demo.text
    demo_pid = demo.json()["id"]
    audit = client.post(f"/projects/{demo_pid}/audit", json={"use_ai": False}).json()
    new_run = client.post(f"/projects/{demo_pid}/analyze").json()
    with SessionLocal() as db:
        ctx = ReportService(db).context(ProjectService(db).get(uuid.UUID(demo_pid)))
        results["report_mixes_runs"] = {"report_analysis_version": ctx["run"].analysis_version, "audit_version_in_report": ctx["audit"]["_version"], "same_analytics_run": str(ctx["run"].id) == audit["analytics_run_id"]}
        assert results["report_mixes_runs"]["same_analytics_run"] is False
    assert new_run["analysis_version"] == 2
    client.put(f"/projects/{demo_pid}", json={"name": "\u0645\u0634\u0631\u0648\u0639"})
    html_export = client.get(f"/projects/{demo_pid}/report?download=true")
    results["unicode_html_export"] = {"http_status": html_export.status_code}
    assert html_export.status_code == 500
    results["unauthenticated_project_access"] = {"list_status": client.get("/projects").status_code, "read_status": client.get(f"/projects/{demo_pid}").status_code, "delete_status": client.delete(f"/projects/{demo_pid}").status_code}

output = ROOT / "review" / "diagnostics-results.json"
output.write_text(json.dumps(results, indent=2, ensure_ascii=True), encoding="utf-8")
print(json.dumps(results, indent=2, ensure_ascii=True))
print(f"Results saved: {output}")
