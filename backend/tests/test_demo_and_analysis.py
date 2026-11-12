import io
import zipfile

from fastapi.testclient import TestClient

from tests.test_api_ingestion import PROJECT


def test_demo_businesses(client: TestClient) -> None:
    items = client.get("/demo/businesses").json()
    assert {b["key"] for b in items} >= {"agency_uae", "cafe_paris", "saas_uk"}


def test_dataset_download_zip(client: TestClient) -> None:
    r = client.post(
        "/demo/dataset", json={"business": "agency_uae", "days": 30, "platforms": ["instagram", "linkedin"]}
    )
    assert r.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert any(n.endswith(".csv") for n in names) and any(n.endswith(".xlsx") for n in names)


def test_demo_end_to_end(client: TestClient) -> None:
    r = client.post("/demo/generate", json={"business": "agency_uae", "days": 90, "seed": 7})
    assert r.status_code == 201, r.text
    project = r.json()
    pid = project["id"]
    assert project["is_demo"] and project["status"] == "analyzed"

    files = client.get(f"/projects/{pid}/files").json()
    assert sorted(f["platform"] for f in files) == ["facebook", "instagram", "linkedin", "tiktok"]
    assert all(f["status"] == "normalized" for f in files)
    # Injected duplicates were caught by validation.
    assert all(any(i["code"] == "duplicate_posts" for i in f["validation"]["issues"]) for f in files)

    a = client.get(f"/projects/{pid}/analytics").json()
    assert a["run"]["analysis_version"] == 1
    s = a["sections"]
    assert set(s) >= {"overview", "platforms", "cross_platform", "findings", "post_metrics", "scoring"}
    assert s["overview"]["total_posts"] == 305
    assert s["platforms"]["instagram"]["kpis"]["exposure_metric"] == "reach"
    assert "total_saves" not in s["platforms"]["linkedin"]["kpis"]["metrics"]
    assert "total_saves" in s["platforms"]["linkedin"]["kpis"]["unavailable"]
    assert s["platforms"]["linkedin"]["timing"]["has_time"] is False
    assert all(f["confidence"] in ("high", "medium", "low") for f in s["findings"])
    assert any(f["p_adjusted"] is not None for f in s["findings"])

    # The planted Reels > Images reach pattern is detected with high confidence.
    reels = [f for f in s["findings"] if f["id"].startswith("format:instagram:exposure:reel_vs")]
    assert reels and reels[0]["confidence"] == "high" and reels[0]["difference_pct"] > 50

    ins = client.get(f"/projects/{pid}/insights").json()["insights"]
    rule_ids = {i["rule_id"] for i in ins}
    assert "posting_gap" in rule_ids  # Facebook has a planted inactivity gap
    assert "content_mix_imbalance" in rule_ids  # Facebook is >50% promotional

    # Versioning: re-analysis creates version 2 and keeps version 1.
    r2 = client.post(f"/projects/{pid}/analyze")
    assert r2.status_code == 200 and r2.json()["analysis_version"] == 2
    assert len(client.get(f"/projects/{pid}/analytics/runs").json()) == 2
    assert client.get(f"/projects/{pid}/analytics?version=1").json()["run"]["analysis_version"] == 1
    subset = client.get(f"/projects/{pid}/analytics?sections=overview").json()["sections"]
    assert list(subset) == ["overview"]

    posts = client.get(f"/projects/{pid}/posts?platform=tiktok&limit=5&sort=views").json()
    assert posts["total"] == 75 and len(posts["items"]) == 5
    assert posts["items"][0]["views"] >= posts["items"][1]["views"]
    assert posts["items"][0]["topic_source"] == "keyword"

    csv_text = client.get(f"/projects/{pid}/export/posts.csv").text
    assert csv_text.startswith("platform,external_post_id")


def test_analyze_without_data_is_clean_error(client: TestClient) -> None:
    pid = client.post("/projects", json=PROJECT).json()["id"]
    r = client.post(f"/projects/{pid}/analyze")
    assert r.status_code == 422 and r.json()["code"] == "invalid_dataset"
    assert client.get(f"/projects/{pid}/analytics").status_code == 404
