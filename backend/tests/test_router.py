import json
import sqlite3

import pytest
from pydantic import ValidationError

from app import router as router_module
from app import study
from app.definitions import EXPERIMENTAL_TASK_MS
from app.router import MockRouter, RouteLLMRouter, RouterError, load_routellm_scorer, routing_prompt
from tests.conftest import Participant, isolated_settings


class Scorer:
    """Stands in for RouteLLM's calculate_strong_win_rate."""

    def __init__(self, *scores):
        self.scores, self.prompts = list(scores), []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        item = self.scores.pop(0)
        if callable(item):
            item = item()
        if isinstance(item, Exception):
            raise item
        return item


def test_routellm_settings_require_an_explicit_threshold_and_key_for_embedding_routers(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="ROUTER_THRESHOLD"):
        isolated_settings(router_mode="routellm", routellm_router="bert")
    with pytest.raises(ValidationError, match="ROUTER_THRESHOLD"):
        isolated_settings(router_mode="routellm", routellm_router="bert", router_threshold=1.5)
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        isolated_settings(router_mode="routellm", routellm_router="mf", router_threshold=0.5)
    assert isolated_settings(router_mode="routellm", routellm_router="bert", router_threshold=0.5).router_threshold == 0.5
    assert isolated_settings().router_mode == "mock"


def test_score_at_or_above_threshold_recommends_large():
    router = RouteLLMRouter("mf", 0.4, Scorer(0.4, 0.39, 1.0, 0.0))
    results = [router.recommend("p", "Venue") for _ in range(4)]
    assert [r.model for r in results] == ["large", "small", "large", "small"]
    assert results[0].reason == "Router estimate: this stage likely needs the large model."
    assert results[1].reason == "Router estimate: the small model is likely enough for this stage."
    assert (results[0].router, results[0].score, results[0].threshold) == ("routellm:mf", 0.4, 0.4)


@pytest.mark.parametrize("bad", [float("nan"), 1.5, -0.1, RuntimeError("sk-secret-in-provider-message")])
def test_router_failures_never_fall_back(bad):
    with pytest.raises(RouterError) as raised:
        RouteLLMRouter("mf", 0.5, Scorer(bad)).recommend("p", "Venue")
    assert "sk-secret" not in str(raised.value)


def test_missing_routellm_package_gives_an_install_hint(monkeypatch):
    monkeypatch.setattr(router_module.os, "environ", {})
    with pytest.raises(RuntimeError, match="requirements-routellm.txt"):
        load_routellm_scorer("bert", None)
    assert router_module.os.environ["OPENAI_API_KEY"] == "not-used-by-this-router"


def test_routing_prompt_describes_stage_requirements_plan_and_questions():
    scenario = {"title": "Company workshop", "requirements": {
        "attendees": 40, "budgetCents": 100000, "dietaryNeeds": ["vegetarian", "gluten-free"], "wheelchairRequired": True}}
    messages = [{"role": "user", "text": f"q{i}"} for i in range(5)] + [{"role": "assistant", "text": "a"}]
    prompt = routing_prompt(scenario, "Catering", {"venue": "A-venue-good", "catering": None, "supplies": []}, messages)
    for expected in ("Catering stage", "Company workshop", "40 guests", "1000.00 USD", "vegetarian, gluten-free",
                     "wheelchair access required", '"venue": "A-venue-good"', "q2 | q3 | q4"):
        assert expected in prompt, expected
    assert "q1" not in prompt


@pytest.fixture
def routed(make_client, tmp_path):
    def make(*scores, threshold=0.5):
        scorer = Scorer(*scores)
        client = make_client(checkpoint_router=RouteLLMRouter("mf", threshold, scorer), dev_controls=True)

        def rows():
            connection = sqlite3.connect(tmp_path / "study.sqlite3")
            connection.row_factory = sqlite3.Row
            result = [dict(row) for row in connection.execute("SELECT * FROM routing_decisions ORDER BY id")]
            connection.close()
            return result
        return client, scorer, rows
    return make


def into_task_1(participant):
    participant.through_practice()
    participant.start()
    return participant


def test_automatic_checkpoint_uses_the_router_score(routed):
    client, scorer, rows = routed(0.8, 0.2)
    participant = into_task_1(Participant(client, 1))
    assert participant.state["routerSimulated"] is False
    decision = participant.route("task-1")
    assert (decision["recommendedModel"], decision["finalModel"]) == ("large", "large")
    assert decision["reason"].startswith("Router estimate")
    participant.call("POST", "/tasks/task-1/routing/recommendation", {"checkpoint": "Venue"})  # repeat: no rescoring
    assert len(scorer.prompts) == 1 and "Venue stage" in scorer.prompts[0]
    participant.call("POST", "/tasks/task-1/checkpoint/advance", {"checkpoint": "Venue"})
    assert participant.route("task-1")["recommendedModel"] == "small"
    (first, second) = rows()
    assert (first["checkpoint"], first["condition"], first["router"], first["score"], first["threshold"],
            first["recommended"], first["ok"], first["applied"]) == ("Venue", "automatic", "routellm:mf", 0.8, 0.5, "large", 1, 1)
    assert json.loads(first["plan"]) == {"venue": None, "catering": None, "supplies": []}
    assert second["checkpoint"] == "Catering" and second["recommended"] == "small"
    assert "score" not in json.dumps(participant.state)  # research data stays server-side


def test_override_concealment_holds_before_any_scoring(routed):
    client, scorer, rows = routed(0.1)
    participant = into_task_1(Participant(client, 3))  # task-1 = A override
    participant.fail("POST", "/tasks/task-1/routing/recommendation", {}, 409, "INVALID_ROUTING_PHASE")
    assert scorer.prompts == [] and rows() == []
    decision = participant.route("task-1", initial="large", final="small")
    assert (decision["initialModel"], decision["recommendedModel"], decision["finalModel"]) == ("large", "small", "small")


def test_router_failure_returns_502_without_a_fallback(routed):
    client, _, rows = routed(RuntimeError("embedding call failed"), 0.9)
    participant = into_task_1(Participant(client, 1))
    participant.fail("POST", "/tasks/task-1/routing/recommendation", {"checkpoint": "Venue"}, 502, "PROVIDER_ERROR")
    venue = client.get(f"/api/sessions/{participant.sid}").json()["tasks"]["task-1"]["decisions"]["Venue"]
    assert venue["recommendedModel"] is None and venue["phase"] == "awaiting-recommendation"
    assert participant.route("task-1")["recommendedModel"] == "large"  # retry works
    assert [(r["ok"], r["applied"], r["recommended"]) for r in rows()] == [(0, 0, None), (1, 1, "large")]
    assert rows()[0]["error"] == "routellm:mf failed (RuntimeError)"


def test_recommendation_ready_after_the_deadline_is_not_applied(routed, clock):
    def late():
        clock.advance(EXPERIMENTAL_TASK_MS)
        return 0.9
    client, _, rows = routed(late)
    participant = into_task_1(Participant(client, 1))
    data = participant.fail("POST", "/tasks/task-1/routing/recommendation", {}, 409, "TASK_EXPIRED")
    assert data["state"]["step"] == "tlx-1"
    assert data["state"]["tasks"]["task-1"]["decisions"]["Venue"]["recommendedModel"] is None
    assert [(r["ok"], r["applied"]) for r in rows()] == [(1, 0)]


def test_recommendation_ready_after_submission_is_not_applied(routed):
    client, _, rows = routed()
    participant = into_task_1(Participant(client, 1))
    store = client.app.state.store

    def submitted_meanwhile():
        store.mutate(participant.sid, lambda c, s, now: study.finish_task(c, s, "task-1", "submitted", now))
        return 0.2
    client.app.state.router._score.scores.append(submitted_meanwhile)
    participant.fail("POST", "/tasks/task-1/routing/recommendation", {}, 409, "NO_ACTIVE_TASK")
    assert [(r["applied"], r["recommended"]) for r in rows()] == [(0, "small")]


def test_mock_router_decisions_are_recorded_too(client):
    participant = into_task_1(Participant(client))
    assert participant.state["routerSimulated"] is True
    participant.route("task-1")
    store_rows = sqlite3.connect(client.app.state.store.path).execute(
        "SELECT router, score, recommended, applied FROM routing_decisions").fetchall()
    assert store_rows[0][0] == "mock" and store_rows[0][1] is None and store_rows[0][3] == 1
    assert MockRouter().recommend("ignored", "Catering").model == "large"
