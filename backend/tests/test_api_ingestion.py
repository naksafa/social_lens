import io

from fastapi.testclient import TestClient

from tests.fixtures import INSTAGRAM_CSV, TIKTOK_CSV, linkedin_xlsx

PROJECT = {
    "name": "Acme audit",
    "platforms": ["instagram", "tiktok", "linkedin"],
    "timezone": "Asia/Dubai",
    "business_profile": {
        "business_name": "Acme Digital",
        "industry": "Marketing agency",
        "country": "UAE",
        "city_market": "Dubai",
        "products_services": "Social media management, paid ads",
        "target_audience": "SME owners",
        "business_objective": "Grow qualified leads",
        "marketing_objectives": ["lead_generation", "engagement"],
    },
}


def _create(client: TestClient) -> str:
    r = client.post("/projects", json=PROJECT)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_project_crud(client: TestClient) -> None:
    pid = _create(client)
    assert client.get(f"/projects/{pid}").json()["business_profile"]["country"] == "UAE"
    r = client.put(f"/projects/{pid}", json={"name": "Renamed", "timezone": "Europe/Paris"})
    assert r.status_code == 200 and r.json()["name"] == "Renamed"
    assert any(p["id"] == pid for p in client.get("/projects").json())
    assert client.delete(f"/projects/{pid}").status_code == 204
    assert client.get(f"/projects/{pid}").status_code == 404


def test_project_validation_errors(client: TestClient) -> None:
    bad = {**PROJECT, "timezone": "Mars/Base", "platforms": []}
    r = client.post("/projects", json=bad)
    assert r.status_code == 422
    assert r.json()["code"] == "validation_error"


def test_full_ingestion_flow(client: TestClient) -> None:
    pid = _create(client)
    files = [
        ("files", ("instagram_export.csv", io.BytesIO(INSTAGRAM_CSV.encode()), "text/csv")),
        ("files", ("tiktok.csv", io.BytesIO(TIKTOK_CSV.encode()), "text/csv")),
        ("files", ("page_updates.xlsx", io.BytesIO(linkedin_xlsx()), "application/octet-stream")),
    ]
    r = client.post(f"/projects/{pid}/files", files=files)
    assert r.status_code == 201, r.text
    uploaded = r.json()
    assert [f["platform"] for f in uploaded] == ["instagram", "tiktok", "linkedin"]
    ig = uploaded[0]
    assert ig["row_count"] == 7
    reach = next(m for m in ig["mappings"] if m["source_column"] == "Reach")
    assert reach["target_field"] == "reach" and reach["confidence"] >= 0.9

    # Duplicate upload is rejected.
    dup = client.post(
        f"/projects/{pid}/files",
        files=[("files", ("again.csv", io.BytesIO(INSTAGRAM_CSV.encode()), "text/csv"))],
    )
    assert dup.status_code == 409

    # Preview
    prev = client.get(f"/projects/{pid}/files/{ig['id']}/preview?limit=3").json()
    assert len(prev["rows"]) == 3 and "Reach" in prev["columns"]

    # Invalid confirmation: two columns -> same field
    bad = client.post(
        f"/projects/{pid}/files/{ig['id']}/mapping/confirm",
        json={
            "platform": "instagram",
            "mappings": [
                {"source_column": "Likes", "target_field": "reach"},
            ],
        },
    )
    assert bad.status_code == 422 and bad.json()["code"] == "mapping_error"

    # Confirm suggested mappings (with one manual correction)
    for f in uploaded:
        items = [{"source_column": m["source_column"], "target_field": m["target_field"]} for m in f["mappings"]]
        if f["platform"] == "instagram":
            items = [i if i["source_column"] != "Account username" else {**i, "target_field": None} for i in items]
        r = client.post(
            f"/projects/{pid}/files/{f['id']}/mapping/confirm",
            json={"platform": f["platform"], "mappings": items},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "mapped"

    r = client.post(f"/projects/{pid}/normalize")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_posts"] == 5 + 3 + 3
    assert all(f["status"] == "normalized" for f in body["files"])

    # Re-normalizing is idempotent (replaces the file's posts).
    assert client.post(f"/projects/{pid}/normalize").json()["total_posts"] == 11
    proj = client.get("/projects").json()
    item = next(p for p in proj if p["id"] == pid)
    assert item["post_count"] == 11 and item["status"] == "normalized"


def test_upload_rejects_bad_extension(client: TestClient) -> None:
    pid = _create(client)
    r = client.post(
        f"/projects/{pid}/files",
        files=[("files", ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream"))],
    )
    assert r.status_code == 415
    assert r.json()["code"] == "unsupported_file_type"


def test_canonical_fields_meta(client: TestClient) -> None:
    fields = client.get("/meta/canonical-fields").json()
    assert any(f["name"] == "published_at" and f["required"] for f in fields)
