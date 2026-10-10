def test_health_reports_mock_mode(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "mock", "router": "mock"}


def test_openapi_and_docs_stay_under_api_prefix(client):
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/docs").status_code == 200
    assert client.get("/docs").status_code == 404
