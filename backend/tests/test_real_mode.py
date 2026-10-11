import json
import sqlite3

import pytest

from app import study
from app.agent import ModelAgent
from app.definitions import EXPERIMENTAL_TASK_MS
from app.models import ModelError
from tests.conftest import Participant
from tests.fakes import FakeOpenAIServer, ScriptedClient, answer, completion, tool

REAL = {"model_mode": "real", "openai_api_key": "sk-test-not-real", "dev_controls": True}


@pytest.fixture
def real(make_client, tmp_path):
    """A real-mode app whose model clients are scripted; returns (client, small, large, calls())."""
    def make(small=(), large=()):
        clients = {"small": ScriptedClient("small", list(small)), "large": ScriptedClient("large", list(large))}
        client = make_client(agent=ModelAgent(clients, max_steps=4), **REAL)

        def calls():
            connection = sqlite3.connect(tmp_path / "study.sqlite3")
            connection.row_factory = sqlite3.Row
            rows = [dict(row) for row in connection.execute("SELECT * FROM model_calls ORDER BY id")]
            connection.close()
            return rows
        return client, clients, calls
    return make


def into_task_1(participant):
    participant.through_practice()
    participant.start()
    participant.route("task-1")  # sequence 1: automatic, Venue recommends small
    return participant


def test_real_reply_is_shown_and_recorded(real):
    client, clients, calls = real(small=[tool("search_catalog", {"category": "venue"}), answer("Try Willow Conference Hall.")])
    assert client.get("/api/health").json() == {"status": "ok", "mode": "real", "router": "mock"}
    participant = into_task_1(Participant(client, 1))
    assert participant.state["simulated"] is False
    data = participant.call("POST", "/tasks/task-1/messages", {"checkpoint": "Venue", "text": "Which venue?"})
    user, reply = participant.task()["messages"]
    assert (user["text"], user["simulated"]) == ("Which venue?", False)
    assert (reply["text"], reply["model"], reply["simulated"]) == ("Try Willow Conference Hall.", "small", False)
    text = json.dumps(data)
    assert "fake-small" not in text and "prompt_tokens" not in text  # research data stays server-side
    rows = calls()
    assert [(r["task_id"], r["checkpoint"], r["size"], r["provider"], r["model"], r["step"], r["ok"], r["shown"])
            for r in rows] == [("task-1", "Venue", "small", "openai", "fake-small", 1, 1, 1),
                               ("task-1", "Venue", "small", "openai", "fake-small", 2, 1, 1)]
    assert json.loads(rows[0]["tools"]) == ["search_catalog"] and rows[1]["prompt_tokens"] == 10
    assert clients["large"].requests == []


def test_large_model_is_used_when_the_stage_locks_it(real):
    client, clients, _ = real(large=[answer("Use Orchard Catering.")])
    participant = into_task_1(Participant(client, 1))
    participant.call("POST", "/tasks/task-1/checkpoint/advance", {"checkpoint": "Venue"})
    assert participant.route("task-1")["finalModel"] == "large"  # Catering recommends large
    participant.call("POST", "/tasks/task-1/messages", {"text": "Catering?"})
    assert participant.task()["messages"][-1]["model"] == "large"
    assert len(clients["large"].requests) == 1 and clients["small"].requests == []


def test_provider_failure_returns_502_and_keeps_state(real):
    client, _, calls = real(small=[ModelError("openai returned HTTP 503"), answer("Back again.")])
    participant = into_task_1(Participant(client, 1))
    before = participant.task()
    participant.fail("POST", "/tasks/task-1/messages", {"text": "Hello?"}, 502, "PROVIDER_ERROR")
    assert client.get(f"/api/sessions/{participant.sid}").json()["tasks"]["task-1"] == before
    assert [(r["ok"], r["shown"], r["error"]) for r in calls()] == [(0, 0, "openai returned HTTP 503")]
    participant.call("POST", "/tasks/task-1/messages", {"text": "Hello?"})  # retry works
    assert participant.task()["messages"][-1]["text"] == "Back again."


def test_reply_after_deadline_is_discarded_and_task_times_out(real, clock):
    def slow(messages):
        clock.advance(EXPERIMENTAL_TASK_MS)
        return answer("Too late.")
    client, _, calls = real(small=[slow])
    participant = into_task_1(Participant(client, 1))
    deadline = participant.task()["deadline"]
    data = participant.fail("POST", "/tasks/task-1/messages", {"text": "Slow question"}, 409, "TASK_EXPIRED")
    task = data["state"]["tasks"]["task-1"]
    assert data["state"]["step"] == "tlx-1" and task["status"] == "timed-out" and task["endedAt"] == deadline
    assert task["messages"] == []
    assert [(r["ok"], r["shown"]) for r in calls()] == [(1, 0)]


def test_reply_for_an_earlier_checkpoint_is_discarded(real):
    client, _, calls = real()
    participant = into_task_1(Participant(client, 1))
    store = client.app.state.store

    def advance_meanwhile(messages):
        store.mutate(participant.sid, lambda c, s, now: study.advance_checkpoint(
            study.planning_task(c, s, "task-1", None, now), now))
        return answer("Venue advice")
    client.app.state.agent.clients["small"].replies.append(advance_meanwhile)
    participant.fail("POST", "/tasks/task-1/messages", {"checkpoint": "Venue", "text": "Venue?"}, 409, "STALE_OPERATION")
    stored = client.get(f"/api/sessions/{participant.sid}").json()["tasks"]["task-1"]
    assert stored["checkpoint"] == "Catering" and stored["messages"] == []
    assert [(r["checkpoint"], r["shown"]) for r in calls()] == [("Venue", 0)]


def test_reply_after_submission_is_discarded(real):
    client, _, calls = real()
    participant = into_task_1(Participant(client, 1))
    store = client.app.state.store

    def submit_meanwhile(messages):
        store.mutate(participant.sid, lambda c, s, now: study.finish_task(c, s, "task-1", "submitted", now))
        return answer("Late")
    client.app.state.agent.clients["small"].replies.append(submit_meanwhile)
    participant.fail("POST", "/tasks/task-1/messages", {"text": "?"}, 409, "NO_ACTIVE_TASK")
    stored = client.get(f"/api/sessions/{participant.sid}").json()
    assert stored["step"] == "tlx-1" and stored["tasks"]["task-1"]["messages"] == []
    assert [r["shown"] for r in calls()] == [0]


def test_practice_uses_the_real_small_model(real):
    client, clients, calls = real(small=[answer("Meadow Hall fits.")])
    participant = Participant(client, 1)
    participant.introduction()
    participant.start()
    participant.call("POST", "/tasks/practice/messages", {"text": "Venue?"})
    assert participant.task()["messages"][-1]["simulated"] is False
    assert "Practice team lunch" in clients["small"].requests[0][0][0]["content"]
    assert calls()[0]["task_id"] == "practice"


def test_real_mode_end_to_end_over_http(make_client, tmp_path):
    """Settings-built clients against a local OpenAI-compatible server (no injected fakes)."""
    server = FakeOpenAIServer([
        (200, completion(tool_calls=[("check_plan", {"venue": "A-venue-good", "catering": None, "supplies": []})])),
        (200, completion(content="Willow Conference Hall works; add catering next.")),
    ])
    try:
        client = make_client(**REAL, small_model="openai:fake-small", large_model="openai:fake-large",
                             openai_base_url=server.url)
        participant = into_task_1(Participant(client, 1))
        participant.call("POST", "/tasks/task-1/messages", {"text": "Is Willow okay?"})
        assert participant.task()["messages"][-1]["text"] == "Willow Conference Hall works; add catering next."
        first, second = server.requests
        assert first["headers"]["Authorization"] == "Bearer sk-test-not-real"
        assert first["body"]["model"] == "fake-small"
        assert {t["function"]["name"] for t in first["body"]["tools"]} == {"search_catalog", "inspect_item", "check_plan"}
        tool_message = second["body"]["messages"][-1]
        assert tool_message["role"] == "tool" and json.loads(tool_message["content"])["constraints"]["capacity"] is True
    finally:
        server.close()
