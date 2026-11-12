from fastapi.testclient import TestClient


def test_health_reports_db_ok_and_ai_not_configured(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"]["status"] == "ok"
    assert body["ai"]["status"] == "not_configured"
    assert body["environment"] == "test"


def test_request_id_header_is_echoed(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"


def test_unknown_route_returns_structured_error(client: TestClient) -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert set(response.json()) == {"code", "message", "details"}
    assert response.json()["code"] == "not_found"


def test_openapi_docs_available(client: TestClient) -> None:
    assert client.get("/openapi.json").status_code == 200
