import json
import re
import sqlite3

import pytest

from app import db, oracle, records
from app.models import ModelError, ModelReply, ToolCall
from app.oracle import STAGE_CHECKS, evaluate_pending, label, propose, stage_passes
from tests.conftest import Participant
from tests.fakes import ScriptedClient, answer, tool

GOOD = {"venue": "A-venue-good", "catering": "A-food-good", "supplies": ["A-supplies-good"]}


def submit(plan: dict, call_id: str = "s1") -> ModelReply:
    return ModelReply(None, [ToolCall(call_id, "submit_plan", json.dumps(plan))], 30, 6)


class StageClient:
    """Oracle double: submits the plan chosen for the stage named in the system prompt."""

    def __init__(self, size, plans_by_checkpoint, fail_on=()):
        self.size, self.provider, self.model = size, "openai", f"oracle-{size}"
        self.plans, self.fail_on, self.requests = plans_by_checkpoint, set(fail_on), []

    def chat(self, messages, tools=None):
        self.requests.append(tools)
        checkpoint = re.search(r"Current stage: (.+?)\. ", messages[0]["content"]).group(1)
        if checkpoint in self.fail_on:
            raise ModelError("openai returned HTTP 500")
        return submit(self.plans[checkpoint])


class ReferenceClient(StageClient):
    """Submits the feasible reference plan of whichever scenario the prompt describes."""

    def __init__(self, size):
        super().__init__(size, {})

    def chat(self, messages, tools=None):
        prefix = "A" if "Company workshop" in messages[0]["content"] else "B"
        return submit({"venue": f"{prefix}-venue-good", "catering": f"{prefix}-food-good",
                       "supplies": [f"{prefix}-supplies-good"]})


@pytest.fixture
def connection(tmp_path):
    path = tmp_path / "oracle.sqlite3"
    db.init_db(path)
    conn = db.connect(path)
    yield conn
    conn.close()


def test_labels_prefer_small_when_it_passes():
    assert [label(s, l) for s, l in [(True, True), (True, False), (False, True), (False, False)]] == \
        ["small", "small", "large", "neither"]


def test_stage_pass_rule_checks_only_planned_stages(connection):
    venue_only = {"venue": "A-venue-good", "catering": None, "supplies": []}
    assert stage_passes(connection, "A", "Venue", venue_only)
    assert not stage_passes(connection, "A", "Catering", venue_only)  # dietary now required
    assert not stage_passes(connection, "A", "Venue", dict(venue_only, venue="A-venue-capacity"))
    assert stage_passes(connection, "A", "Supplies", GOOD) and stage_passes(connection, "A", "Final constraint check", GOOD)
    over_budget = dict(GOOD, supplies=["A-supplies-good", "A-supplies-cost"])
    assert stage_passes(connection, "A", "Catering", over_budget)  # budget not yet checked
    assert not stage_passes(connection, "A", "Supplies", over_budget)
    assert not stage_passes(connection, "A", "Venue", {"venue": "B-venue-good", "catering": None, "supplies": []})
    assert not stage_passes(connection, "A", "Venue", None)


def test_location_is_checked_at_every_stage(connection):
    assert all("location" in checks for checks in STAGE_CHECKS.values())
    elsewhere = dict(GOOD, venue="A-venue-08")  # North Quarter is required; this venue is in Old Town
    for checkpoint in STAGE_CHECKS:
        assert not stage_passes(connection, "A", checkpoint, elsewhere), checkpoint


def test_proposal_uses_tools_then_submit(connection):
    scenario = {"id": "A", "title": "Company workshop", "requirements": {
        "attendees": 40, "budgetCents": 100000, "dietaryNeeds": ["vegetarian"], "wheelchairRequired": True,
        "requiredSupplies": ["name cards"], "area": {"id": "north-quarter", "name": "North Quarter"}}}
    client = ScriptedClient("small", [tool("search_catalog", {"category": "venue"}), submit(GOOD)])
    proposal = propose(client, connection, scenario, "Final constraint check", GOOD | {"supplies": []}, 3)
    assert proposal.plan == GOOD and proposal.passed and [c.tools for c in proposal.calls] == [["search_catalog"], ["submit_plan"]]
    no_submit = propose(ScriptedClient("small", [answer("Pick Willow."), answer("Still no structured plan.")]), connection, scenario, "Venue", GOOD, 3)
    assert (no_submit.plan, no_submit.passed) == (None, False)
    looping = ScriptedClient("small", [tool("search_catalog", {}) for _ in range(3)])
    bounded = propose(looping, connection, scenario, "Venue", GOOD, 2)
    assert bounded.plan is None and len(looping.requests) == 3
    assert looping.requests[-1][1] is None  # Last call finalizes JSON, with no callable tools.
    assert bounded.request_overrides == [{"step": 3, "messages": looping.requests[-1][0], "format": "stage-plan-json-v1"}]
    facts = json.loads(looping.requests[-1][0][1]["content"])
    assert facts["current_plan"] == GOOD
    assert all("capacity" not in item for item in facts["observed_catalog_items"])  # No uninspected detail injection.
    bad = propose(ScriptedClient("small", [ModelReply(None, [ToolCall("x", "submit_plan", "not json")])]),
                  connection, scenario, "Venue", GOOD, 2)
    assert (bad.plan, bad.passed) == (None, False)


def test_terminal_json_collects_a_real_proposal_without_an_extra_call(connection):
    scenario = json.loads(connection.execute("SELECT data FROM catalog_scenarios WHERE id='A'").fetchone()[0])
    partial = {"venue": "A-venue-good", "catering": None, "supplies": []}
    client = ScriptedClient("small", [tool("search_catalog", {"category": "venue"}),
        tool("inspect_item", {"item_id": "A-venue-good"}), answer(json.dumps(partial))])
    proposal = propose(client, connection, scenario, "Venue", {"venue": None, "catering": None, "supplies": []}, 2)
    assert proposal.passed and proposal.plan == partial and len(proposal.calls) == 3
    assert client.requests[-1][1] is None
    facts = json.loads(client.requests[-1][0][1]["content"])
    by_id = {item["id"]: item for item in facts["observed_catalog_items"]}
    assert by_id["A-venue-good"]["capacity"] == 40
    assert "capacity" not in by_id["A-venue-capacity"]
    assert "Pick Willow" not in client.requests[-1][0][0]["content"]


def test_early_prose_gets_one_bounded_structured_completion(connection):
    scenario = json.loads(connection.execute("SELECT data FROM catalog_scenarios WHERE id='A'").fetchone()[0])
    client = ScriptedClient("small", [tool("inspect_item", {"item_id": "A-venue-good"}),
        answer("Use the inspected venue."), answer(json.dumps(GOOD))])
    proposal = propose(client, connection, scenario, "Venue", GOOD, 8)
    assert proposal.passed and proposal.plan == GOOD and len(proposal.calls) == 3
    assert client.requests[-1][1] is None
    assert proposal.request_overrides[0]["step"] == 3
    facts = json.loads(client.requests[-1][0][1]["content"])
    assert [item["id"] for item in facts["observed_catalog_items"]] == ["A-venue-good"]
    assert facts["observed_catalog_items"][0]["capacity"] == 40


@pytest.mark.parametrize("supplies", ["A-supplies-good", 0, ["A-supplies-good", "A-supplies-good"]])
def test_plan_parser_does_not_repair_invalid_supply_choices(supplies):
    assert oracle.parsed_plan(dict(GOOD, supplies=supplies)) is None


def test_proposal_replays_provider_continuation(connection):
    scenario = json.loads(connection.execute("SELECT data FROM catalog_scenarios WHERE id='A'").fetchone()[0])
    first = tool("inspect_item", {"item_id": "A-venue-good"})
    first.continuation["reasoning"] = "synthetic continuation state"
    client = ScriptedClient("small", [first, submit(GOOD)])
    proposal = propose(client, connection, scenario, "Venue", GOOD, 4)
    assert proposal.passed
    assert client.requests[1][0][2]["reasoning"] == "synthetic continuation state"


@pytest.fixture
def routed_session(dev_client):
    """Sequence 1 task-1 (A automatic): all four checkpoints routed and recorded."""
    participant = Participant(dev_client, 1)
    participant.through_practice()
    participant.start()
    for index, checkpoint in enumerate(["Venue", "Catering", "Supplies", "Final constraint check"]):
        participant.route("task-1")
        if index < 3:
            participant.call("POST", "/tasks/task-1/checkpoint/advance", {"checkpoint": checkpoint})
    return dev_client, participant


def rows(store, sql):
    connection = sqlite3.connect(store.path)
    connection.row_factory = sqlite3.Row
    result = [dict(row) for row in connection.execute(sql)]
    connection.close()
    return result


def test_paired_evaluation_labels_all_four_cases_and_stays_hidden(routed_session):
    client, participant = routed_session
    store = client.app.state.store
    before = client.get(f"/api/sessions/{participant.sid}").json()
    venue_bad = dict(GOOD, venue="A-venue-access")
    small = StageClient("small", {"Venue": GOOD, "Catering": GOOD, "Supplies": venue_bad, "Final constraint check": venue_bad})
    large = StageClient("large", {"Venue": GOOD, "Catering": venue_bad, "Supplies": GOOD, "Final constraint check": venue_bad})
    results = evaluate_pending(store, {"small": small, "large": large}, max_steps=3)
    assert [(r["checkpoint"], r["small_passed"], r["large_passed"], r["label"]) for r in results] == [
        ("Venue", True, True, "small"), ("Catering", True, False, "small"),
        ("Supplies", False, True, "large"), ("Final constraint check", False, False, "neither")]
    stored = rows(store, "SELECT checkpoint, small_plan, label FROM oracle_results ORDER BY id")
    assert json.loads(stored[2]["small_plan"]) == venue_bad and [r["label"] for r in stored] == ["small", "small", "large", "neither"]
    usage = rows(store, "SELECT purpose, size, shown, COUNT(*) AS n FROM model_calls GROUP BY purpose, size, shown")
    assert usage == [{"purpose": "oracle", "size": "large", "shown": 0, "n": 4},
                     {"purpose": "oracle", "size": "small", "shown": 0, "n": 4}]
    after = client.get(f"/api/sessions/{participant.sid}").json()
    assert after == before and "oracle" not in json.dumps(after)
    assert evaluate_pending(store, {"small": small, "large": large}, max_steps=3) == []  # nothing re-evaluated


def test_failed_checkpoints_stay_pending_and_record_usage(routed_session):
    client, _ = routed_session
    store = client.app.state.store
    small = StageClient("small", {cp: GOOD for cp in oracle.STAGE_CHECKS})
    large = StageClient("large", {cp: GOOD for cp in oracle.STAGE_CHECKS}, fail_on={"Supplies"})
    results = evaluate_pending(store, {"small": small, "large": large}, max_steps=3)
    assert [r.get("error") for r in results] == [None, None, "large model call failed", None]
    assert len(rows(store, "SELECT * FROM oracle_results")) == 3
    failed = rows(store, "SELECT size, ok FROM model_calls WHERE checkpoint = 'Supplies' ORDER BY id")
    assert failed == [{"size": "small", "ok": 1}, {"size": "large", "ok": 0}]
    large.fail_on.clear()
    retry = evaluate_pending(store, {"small": small, "large": large}, max_steps=3)
    assert [(r["checkpoint"], r["label"]) for r in retry] == [("Supplies", "small")]


def test_old_databases_gain_the_purpose_column(tmp_path):
    path = tmp_path / "old.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE model_calls (id INTEGER PRIMARY KEY, session_id TEXT, task_id TEXT, checkpoint TEXT,"
                       " size TEXT, provider TEXT, model TEXT, step INTEGER, ok INTEGER, error TEXT, prompt_tokens INTEGER,"
                       " completion_tokens INTEGER, latency_ms INTEGER, tools TEXT, shown INTEGER, created_at INTEGER)")
    connection.execute("INSERT INTO model_calls (session_id, size, ok, shown) VALUES ('s', 'small', 1, 1)")
    connection.commit()
    connection.close()
    db.init_db(path)
    connection = sqlite3.connect(path)
    assert connection.execute("SELECT purpose FROM model_calls").fetchall() == [("participant",)]
    connection.close()


def test_oracle_command_requires_real_mode(capsys):
    assert oracle.main([]) == 2
    assert "MODEL_MODE=real" in capsys.readouterr().out


def test_records_summary_counts_completed_participants(make_client):
    client = make_client()
    finished = []
    for _ in range(4):
        participant = Participant(client)
        participant.through_practice()
        for task_id in ("task-1", "task-2"):
            participant.start()
            participant.route(task_id, initial="large", final="small")
            participant.call("POST", f"/tasks/{task_id}/finish", {"reason": "submitted"})
            participant.survey(task_id, [25, 0, 50, 75, 25, 0])
        participant.call("POST", "/feedback", {"interfaceComments": "", "studyComments": ""})
        finished.append(participant)
    Participant(client).call("POST", "/consent", {"accepted": True})  # one in progress
    dev = make_client(dev_controls=True)
    Participant(dev, 2)  # development session: excluded
    store = client.app.state.store
    evaluate_pending(store, {"small": ReferenceClient("small"), "large": ReferenceClient("large")}, max_steps=3)

    summary = records.summarize(store.path)
    assert sum(summary["allocation"]["used"].values()) == 5 and summary["allocation"]["free"] == 7
    assert summary["sessions"]["study"] == 5 and summary["sessions"]["development"] == 1
    assert summary["sessions"]["byStep"] == {"completion": 4, "demographics": 1}
    first = next(p for p in summary["participants"] if p["step"] == "completion")
    assert first["step"] == "completion" and len(first["tasks"]) == 2
    task = first["tasks"][0]
    assert task["status"] == "submitted" and task["checkpointsReached"] == 1 and task["constraintsMet"] == 1
    assert task["workloadScore"] == pytest.approx(175 / 6)
    override_changes = sum(t["overrideChanges"] for p in summary["participants"] for t in p["tasks"])
    assert override_changes == 4  # one override task each, initial large -> final small
    assert sum(summary["routing"].values()) == 8
    assert summary["oracle"]["labels"] == {"small": 8} and summary["oracle"]["pending"] == 0
    assert summary["oracle"]["agreement"] == {"final matches oracle": 8}
    assert summary["modelUsage"]["oracle"]["shown"] == 0 and "participant" not in summary["modelUsage"]
    report = records.format_report(summary)
    assert "Oracle: labels" in report and "P0" in report and "dev-" not in report
