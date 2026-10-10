import json

from app.db import init_db
from app.definitions import FIXTURES
from tests.conftest import Participant

REFERENCE_PLANS = json.loads((FIXTURES / "reference-plans.json").read_text())["plans"]


def test_scenarios_and_unknown_ids(client):
    assert client.get("/api/scenarios/A").json()["requirements"]["attendees"] == 40
    assert client.get("/api/scenarios/C").json()["error"]["code"] == "INVALID_REQUEST"


def test_search_returns_summaries_only_in_fixture_order(client):
    results = client.get("/api/scenarios/practice/catalog").json()
    assert len(results) == 8
    assert results[0]["id"] == "practice-venue-good"
    assert set(results[0]) == {"id", "scenarioId", "category", "name", "summary", "priceCents"}
    venues = client.get("/api/scenarios/A/catalog", params={"category": "venue"}).json()
    assert [item["id"] for item in venues] == ["A-venue-good", "A-venue-capacity", "A-venue-access"]
    meadow = client.get("/api/scenarios/practice/catalog", params={"query": "MEADOW"}).json()
    assert [item["name"] for item in meadow] == ["Meadow Hall"]
    assert client.get("/api/scenarios/B/catalog", params={"query": "nothing-matches"}).json() == []


def test_seeding_twice_is_safe(tmp_path):
    path = tmp_path / "seed.sqlite3"
    init_db(path)
    init_db(path)
    import sqlite3
    connection = sqlite3.connect(path)
    assert connection.execute("SELECT COUNT(*) FROM catalog_items").fetchone()[0] == 24
    assert connection.execute("SELECT COUNT(*) FROM allocation_slots").fetchone()[0] == 12
    connection.close()


def test_reference_plans_pass_and_each_distractor_breaks_one_constraint(dev_client):
    # Distractor -> the single constraint it should break when swapped into the reference plan.
    distractors = {"venue-capacity": "capacity", "venue-access": "accessibility",
                   "food-diet": "dietary", "food-servings": "dietary", "supplies-cost": "budget"}
    expected_totals = {"practice": 35000, "A": 80000, "B": 120000}
    for sequence_id, scenario, task_id in ((1, "A", "task-1"), (2, "B", "task-1")):
        participant = Participant(dev_client, sequence_id)
        participant.through_practice()
        participant.start()
        plan = REFERENCE_PLANS[scenario]
        participant.call("PUT", f"/tasks/{task_id}/plan", {"plan": plan})
        assert participant.task()["totalCostCents"] == expected_totals[scenario]
        assert all(participant.task()["constraints"].values())
        for suffix, broken in distractors.items():
            item_id = f"{scenario}-{suffix}"
            changed = dict(plan, supplies=list(plan["supplies"]))
            if suffix.startswith("venue"):
                changed["venue"] = item_id
            elif suffix.startswith("food"):
                changed["catering"] = item_id
            else:
                changed["supplies"].append(item_id)
            participant.call("PUT", f"/tasks/{task_id}/plan", {"plan": changed})
            failing = [name for name, ok in participant.task()["constraints"].items() if not ok]
            assert failing == [broken], (item_id, failing)


def test_inspection_reveals_details_and_records_item_once(dev_client):
    participant = Participant(dev_client, 1)
    participant.introduction()
    participant.start()
    data = participant.call("POST", "/tasks/practice/inspect", {"itemId": "practice-venue-capacity"})
    assert data["item"]["capacity"] == 10
    participant.call("POST", "/tasks/practice/inspect", {"itemId": "practice-venue-capacity"})
    assert participant.task()["inspectedItems"] == ["practice-venue-capacity"]
    participant.fail("POST", "/tasks/practice/inspect", {"itemId": "A-venue-good"}, 404, "NOT_FOUND")
    participant.fail("PUT", "/tasks/practice/plan",
                     {"plan": {"venue": "practice-food-good", "catering": None, "supplies": []}}, 400, "INVALID_PLAN")
