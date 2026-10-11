from tests.conftest import isolated_settings


def preflight(client, origin):
    return client.options("/api/sessions", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})


def test_local_frontend_origins_are_allowed(client):
    for origin in ("http://127.0.0.1:5173", "http://localhost:4173"):
        response = preflight(client, origin)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
    simple = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert simple.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_other_origins_are_not_allowed(client):
    response = preflight(client, "https://example.com")
    assert "access-control-allow-origin" not in response.headers


def test_origins_are_configurable():
    settings = isolated_settings(cors_origins=" http://a.test , ,http://b.test ")
    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]


def test_error_responses_are_readable_by_the_frontend(client):
    response = client.get("/api/sessions/missing", headers={"Origin": "http://127.0.0.1:5173"})
    assert response.status_code == 404
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"
