from fastapi.testclient import TestClient


def test_report_html_and_pdf_fallback(client: TestClient) -> None:
    pid = client.post("/demo/generate", json={"business": "cafe_paris", "days": 90, "seed": 5}).json()["id"]
    # Report works with analytics only...
    r = client.get(f"/projects/{pid}/report")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "Methodology" in r.text and "Benjamini-Hochberg" in r.text and "<svg" in r.text
    assert "Recommendations are based on available historical data" in r.text
    # ...and includes AI sections once generated.
    client.post(f"/projects/{pid}/audit")
    client.post(f"/projects/{pid}/strategy")
    client.post(f"/projects/{pid}/content-plan")
    r = client.get(f"/projects/{pid}/report?download=true")
    assert "30-day content plan" in r.text and "Recommended strategy" in r.text
    assert "attachment" in r.headers["content-disposition"]
    pdf = client.get(f"/projects/{pid}/report?format=pdf")
    assert pdf.status_code in (200, 501)
    if pdf.status_code == 501:
        assert pdf.json()["code"] == "feature_unavailable"


def test_report_requires_analysis(client: TestClient) -> None:
    from tests.test_api_ingestion import PROJECT

    pid = client.post("/projects", json=PROJECT).json()["id"]
    r = client.get(f"/projects/{pid}/report")
    assert r.status_code == 500 and r.json()["code"] == "report_generation_error"
