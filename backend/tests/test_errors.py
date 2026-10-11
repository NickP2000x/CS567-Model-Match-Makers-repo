from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from app.errors import ApiError
from app.main import create_app
from tests.conftest import isolated_settings


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accepted: bool


def client_with_probe_routes() -> TestClient:
    app = create_app(isolated_settings())

    @app.post("/api/probe/body")
    def body(_: Body) -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/probe/conflict")
    def conflict() -> None:
        raise ApiError(409, "INVALID_STEP", "Consent is the first step.")

    @app.get("/api/probe/crash")
    def crash() -> None:
        raise RuntimeError("provider said: sk-secret-value")

    return TestClient(app, raise_server_exceptions=False)


def test_unknown_route_uses_error_envelope(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Not found."}}


def test_wrong_method_uses_error_envelope(client):
    response = client.post("/api/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_validation_failures_become_invalid_request():
    client = client_with_probe_routes()
    for body in ({}, {"accepted": "maybe"}, {"accepted": True, "extra": 1}):
        response = client.post("/api/probe/body", json=body)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_api_error_keeps_contract_code_and_message():
    response = client_with_probe_routes().get("/api/probe/conflict")
    assert response.status_code == 409
    assert response.json() == {"error": {"code": "INVALID_STEP", "message": "Consent is the first step."}}


def test_unexpected_errors_hide_internal_details(caplog):
    response = client_with_probe_routes().get("/api/probe/crash")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "sk-secret-value" not in response.text
    assert "sk-secret-value" not in caplog.text
