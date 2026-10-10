from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from app.store import Store
from tests.conftest import Participant

ASSIGNMENTS = {
    1: [("A", "automatic"), ("B", "override")], 2: [("B", "automatic"), ("A", "override")],
    3: [("A", "override"), ("B", "automatic")], 4: [("B", "override"), ("A", "automatic")],
}


def test_twelve_sessions_are_balanced_then_allocation_is_full(client):
    states = [client.post("/api/sessions", json={}).json() for _ in range(12)]
    assert Counter(state["sequenceId"] for state in states) == {1: 3, 2: 3, 3: 3, 4: 3}
    assert sorted(state["participantId"] for state in states) == [f"P{n:02d}" for n in range(1, 13)]
    for state in states:
        pairs = [(a["scenarioId"], a["condition"]) for a in state["assignments"]]
        assert pairs == ASSIGNMENTS[state["sequenceId"]]
    response = client.post("/api/sessions", json={})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALLOCATION_FULL"


def test_concurrent_creation_never_shares_a_slot(tmp_path):
    store = Store(tmp_path / "race.sqlite3")
    with ThreadPoolExecutor(max_workers=8) as pool:
        states = list(pool.map(lambda _: store.create_session(), range(12)))
    assert len({state["participantId"] for state in states}) == 12
    assert Counter(state["sequenceId"] for state in states) == {1: 3, 2: 3, 3: 3, 4: 3}


def test_resume_returns_same_session_across_app_restarts(make_client):
    participant = Participant(make_client())
    participant.call("POST", "/consent", {"accepted": True})
    restarted = make_client()  # same database file, new app instance
    state = restarted.get(f"/api/sessions/{participant.sid}").json()
    assert state == participant.state
    assert state["step"] == "demographics"
    assert restarted.get("/api/sessions/unknown").json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_consent_comes_first_and_skips_are_rejected(client):
    participant = Participant(client)
    participant.fail("POST", "/demographics", {"age": 25, "gender": "x", "priorLlmUsage": "weekly"},
                     409, "INVALID_STEP")
    participant.fail("POST", "/tutorial/complete", None, 409, "INVALID_STEP")
    participant.fail("POST", "/tasks/practice/begin", None, 409, "INVALID_STEP")
    participant.call("POST", "/consent", {"accepted": False})
    assert participant.step == "consent" and participant.state["consent"] is False
    participant.call("POST", "/consent", {"accepted": True})
    participant.fail("POST", "/demographics", {"age": -1, "gender": "x", "priorLlmUsage": "weekly"},
                     400, "INVALID_DEMOGRAPHICS")
    participant.fail("POST", "/demographics", {"age": 25, "gender": "  ", "priorLlmUsage": "weekly"},
                     400, "INVALID_DEMOGRAPHICS")
    participant.fail("POST", "/demographics", {"age": 25, "gender": "x"}, 400, "INVALID_REQUEST")
    assert participant.state["demographics"] is None


def test_preparations_gate_tutorial_and_tasks(client, clock):
    participant = Participant(client)
    participant.call("POST", "/consent", {"accepted": True})
    participant.call("POST", "/demographics", {"age": 25, "gender": "x", "priorLlmUsage": "never"})
    participant.fail("POST", "/tutorial/complete", None, 409, "INVALID_PREPARATION")
    participant.fail("POST", "/preparations/before-start", {"acknowledgedIds": ["no-refresh"]},
                     400, "INVALID_PREPARATION")
    participant.fail("POST", "/preparations/practice", {"acknowledgedIds": ["untimed", "excluded"]},
                     409, "INVALID_STEP")
    participant.acknowledge("before-start")
    first = participant.state["preparations"]["before-start"]
    assert first["acknowledgedIds"] == ["no-refresh", "synthetic-only"] and first["confirmedAt"] == clock.now
    clock.advance(5000)
    participant.acknowledge("before-start")  # duplicate keeps the original record
    assert participant.state["preparations"]["before-start"] == first
    participant.call("POST", "/tutorial/complete")
    participant.fail("POST", "/tasks/practice/begin", None, 409, "INVALID_PREPARATION")
    participant.acknowledge("practice")
    assert participant.state["tasks"] == {}  # acknowledging creates no task or deadline


def test_development_sequence_selection_and_reset(client, dev_client):
    response = client.post("/api/sessions", json={"sequenceId": 2})
    assert response.status_code == 400 and response.json()["error"]["code"] == "INVALID_REQUEST"
    participant = Participant(client)
    assert client.post(f"/api/sessions/{participant.sid}/reset", json={}).status_code == 404

    dev = Participant(dev_client, 3)
    assert dev.state["sequenceId"] == 3 and dev.state["participantId"].startswith("dev-")
    assert dev_client.post("/api/sessions", json={"sequenceId": 9}).json()["error"]["code"] == "INVALID_SEQUENCE"
    dev.call("POST", "/consent", {"accepted": True})
    fresh = dev_client.post(f"/api/sessions/{dev.sid}/reset", json={"sequenceId": 4}).json()
    assert fresh["sessionId"] != dev.sid and fresh["sequenceId"] == 4 and fresh["step"] == "consent"
    # Development sessions never use allocation slots: the 11 slots left after `participant` remain.
    states = [dev_client.post("/api/sessions", json={}).json() for _ in range(11)]
    assert all(state["participantId"].startswith("P") for state in states)
