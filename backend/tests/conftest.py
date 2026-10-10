import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.definitions import PREPARATIONS
from app.main import create_app

START = 1_791_504_000_000  # 2026-10-09T00:00:00Z, synthetic


def isolated_settings(**overrides) -> Settings:
    # Ignore any developer .env so tests always run in key-free mock mode.
    return Settings(_env_file=None, **overrides)


class Clock:
    """Controllable server clock in epoch milliseconds."""

    def __init__(self, now: int = START):
        self.now = now

    def __call__(self) -> int:
        return self.now

    def advance(self, ms: int) -> None:
        self.now += ms


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def make_client(tmp_path, clock):
    def make(agent=None, checkpoint_router=None, **overrides) -> TestClient:
        settings = isolated_settings(database_path=tmp_path / "study.sqlite3", **overrides)
        return TestClient(create_app(settings, clock, agent, checkpoint_router))
    return make


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def dev_client(make_client) -> TestClient:
    return make_client(dev_controls=True)


class Participant:
    """Drives one synthetic session through the HTTP API and keeps the latest state."""

    def __init__(self, client: TestClient, sequence_id: int | None = None):
        response = client.post("/api/sessions", json={"sequenceId": sequence_id} if sequence_id else {})
        assert response.status_code == 201, response.text
        self.client = client
        self.state = response.json()
        self.sid = self.state["sessionId"]

    def call(self, method: str, path: str, body: dict | None = None, expect: int = 200) -> dict:
        response = self.client.request(method, f"/api/sessions/{self.sid}{path}", json=body)
        assert response.status_code == expect, response.text
        data = response.json()
        if response.status_code < 300:
            self.state = data["state"] if "item" in data else data
        elif "state" in data:
            self.state = data["state"]
        return data

    def fail(self, method: str, path: str, body: dict | None, status: int, code: str) -> dict:
        data = self.call(method, path, body, expect=status)
        assert data["error"]["code"] == code, data
        return data

    @property
    def step(self) -> str:
        return self.state["step"]

    def task(self, task_id: str | None = None) -> dict:
        return self.state["tasks"][task_id or self.step]

    def acknowledge(self, preparation_id: str) -> None:
        ids = [statement["id"] for statement in PREPARATIONS[preparation_id]["statements"]]
        self.call("POST", f"/preparations/{preparation_id}", {"acknowledgedIds": ids})

    def introduction(self) -> None:
        self.call("POST", "/consent", {"accepted": True})
        self.call("POST", "/demographics", {"age": 25, "gender": "synthetic example", "priorLlmUsage": "weekly"})
        self.acknowledge("before-start")
        self.call("POST", "/tutorial/complete")

    def start(self) -> str:
        task_id = self.step
        self.acknowledge(task_id)
        self.call("POST", f"/tasks/{task_id}/begin")
        return task_id

    def through_practice(self) -> None:
        self.introduction()
        self.start()
        self.call("POST", "/tasks/practice/finish", {"reason": "submitted"})
        assert self.step == "task-1"

    def route(self, task_id: str, initial: str = "large", final: str = "small") -> dict:
        """Complete routing at the current checkpoint for the task's condition."""
        task = self.task(task_id)
        checkpoint = {"checkpoint": task["checkpoint"]}
        if task["condition"] == "override":
            self.call("POST", f"/tasks/{task_id}/routing/initial", {**checkpoint, "model": initial})
            self.call("POST", f"/tasks/{task_id}/routing/recommendation", checkpoint)
            self.call("POST", f"/tasks/{task_id}/routing/confirm", {**checkpoint, "model": final})
        else:
            self.call("POST", f"/tasks/{task_id}/routing/recommendation", checkpoint)
        return self.task(task_id)["decisions"][checkpoint["checkpoint"]]

    def survey(self, task_id: str, values: list[int]) -> None:
        dimensions = ["mentalDemand", "physicalDemand", "temporalDemand", "performance", "effort", "frustration"]
        self.call("PUT", f"/surveys/{task_id}", {"answers": dict(zip(dimensions, values))})
        self.call("POST", f"/surveys/{task_id}/submit")
