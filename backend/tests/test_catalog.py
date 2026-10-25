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
    assert [item["id"] for item in venues] == ["A-venue-good", "A-venue-capacity", "A-venue-access",
                                             "A-venue-economy", "A-venue-premium", "A-venue-near-capacity"]
    meadow = client.get("/api/scenarios/practice/catalog", params={"query": "MEADOW"}).json()
    assert [item["name"] for item in meadow] == ["Meadow Hall"]
    assert client.get("/api/scenarios/B/catalog", params={"query": "nothing-matches"}).json() == []


def test_seeding_twice_is_safe(tmp_path):
    path = tmp_path / "seed.sqlite3"
    init_db(path)
    init_db(path)
    import sqlite3
    connection = sqlite3.connect(path)
    assert connection.execute("SELECT COUNT(*) FROM catalog_items").fetchone()[0] == 44
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


def test_expanded_catalog_plans_search_and_distractors(dev_client):
    alternatives = json.loads((FIXTURES / "reference-plans.json").read_text())["alternatives"]
    for sequence, scenario, totals in ((1, "A", [62500, 89000]), (2, "B", [102500, 129000])):
        participant = Participant(dev_client, sequence)
        participant.through_practice()
        participant.start()
        prefix = f"/api/scenarios/{scenario}/catalog"
        for category in ("venue", "catering", "supplies"):
            summaries = dev_client.get(prefix, params={"category": category}).json()
            assert len(summaries) == 6
            assert all(set(item) == {"id", "scenarioId", "category", "name", "summary", "priceCents"}
                       for item in summaries)
        for plan, total in zip(alternatives[scenario], totals):
            participant.call("PUT", "/tasks/task-1/plan", {"plan": plan})
            assert participant.task()["totalCostCents"] == total
            assert all(participant.task()["constraints"].values())
        reference = REFERENCE_PLANS[scenario]
        variants = [
            (dict(reference, venue=f"{scenario}-venue-near-capacity"), "capacity"),
            (dict(reference, catering=f"{scenario}-food-partial"), "dietary"),
            (dict(reference, supplies=[f"{scenario}-supplies-bundle", f"{scenario}-supplies-good"]), "budget"),
        ]
        for plan, constraint in variants:
            participant.call("PUT", "/tasks/task-1/plan", {"plan": plan})
            assert [key for key, met in participant.task()["constraints"].items() if not met] == [constraint]
        participant.call("PUT", "/tasks/task-1/plan", {"plan": dict(reference, supplies=[])})
        assert all(participant.task()["constraints"].values())
        item = participant.call("POST", "/tasks/task-1/inspect", {"itemId": f"{scenario}-food-partial"})["item"]
        assert len(item["dietaryCoverage"]) == 1
        found = dev_client.get(prefix, params={"category": "catering", "query": item["name"].upper()}).json()
        assert [result["id"] for result in found] == [item["id"]]


def test_reseeding_preserves_saved_sessions_and_legacy_catalog_facts(tmp_path):
    import sqlite3
    path = tmp_path / "saved.sqlite3"
    init_db(path)
    with sqlite3.connect(path) as connection:
        # Representative earlier state, including v1 acknowledgement wording.
        saved = json.dumps({"step": "completion", "tasks": {"task-1": {"plan": REFERENCE_PLANS["A"]}},
                            "preparations": {"before-start": {"version": "provisional-before-start-v1",
                                "statements": [{"id": "no-refresh", "text": "Earlier recorded wording"}]}}})
        connection.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
                           ("earlier-run", "synthetic", 1, 1, saved, 1000, 2000))
        # Simulate the old catalog containing only its original eight items per scenario.
        connection.execute("DELETE FROM catalog_items WHERE id LIKE '%-economy' OR id LIKE '%-premium' "
                           "OR id LIKE '%-near-capacity' OR id LIKE '%-buffet' OR id LIKE '%-partial' "
                           "OR id LIKE '%-stationery' OR id LIKE '%-presentation' OR id LIKE '%-tableware' "
                           "OR id LIKE '%-bundle'")
        fields = ("priceCents", "capacity", "wheelchairAccessible", "servings", "dietaryCoverage")
        earlier = {row[0]: {key: json.loads(row[1])[key] for key in fields if key in json.loads(row[1])}
                   for row in connection.execute("SELECT id, data FROM catalog_items")}
        assert len(earlier) == 24
    init_db(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT state, created_at, updated_at FROM sessions").fetchone() == (saved, 1000, 2000)
        for item_id, facts in earlier.items():
            item = json.loads(connection.execute("SELECT data FROM catalog_items WHERE id=?", (item_id,)).fetchone()[0])
            assert {key: item[key] for key in fields if key in item} == facts
        assert connection.execute("SELECT COUNT(*) FROM catalog_items").fetchone()[0] == 44
