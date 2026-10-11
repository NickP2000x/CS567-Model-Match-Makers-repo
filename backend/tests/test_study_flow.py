import pytest

from app.definitions import CHECKPOINTS, EXPERIMENTAL_TASK_MS
from tests.conftest import Participant

PLAN_A = {"venue": "A-venue-good", "catering": None, "supplies": []}


@pytest.mark.parametrize("sequence_id", [1, 2, 3, 4])
def test_full_sequence_from_consent_to_completion(dev_client, sequence_id):
    participant = Participant(dev_client, sequence_id)
    participant.introduction()
    participant.start()
    practice = participant.task("practice")
    assert practice["excludedFromResults"] and practice["deadline"] is None
    assert practice["decisions"]["Venue"]["finalModel"] == "small"
    participant.call("POST", "/tasks/practice/finish", {"reason": "submitted"})
    assert participant.step == "task-1"  # no practice survey

    for task_id, survey_step in (("task-1", "tlx-1"), ("task-2", "tlx-2")):
        participant.start()
        task = participant.task(task_id)
        assignment = participant.state["assignments"][0 if task_id == "task-1" else 1]
        assert (task["scenarioId"], task["condition"]) == (assignment["scenarioId"], assignment["condition"])
        assert task["deadline"] == task["startedAt"] + EXPERIMENTAL_TASK_MS
        for position, checkpoint in enumerate(CHECKPOINTS):
            decision = participant.route(task_id)
            assert decision["phase"] == "committed"
            participant.call("POST", f"/tasks/{task_id}/messages", {"checkpoint": checkpoint, "text": "Compare options"})
            if position < len(CHECKPOINTS) - 1:
                participant.call("POST", f"/tasks/{task_id}/checkpoint/advance", {"checkpoint": checkpoint})
        participant.fail("POST", f"/tasks/{task_id}/checkpoint/advance", {}, 409, "FINAL_CHECKPOINT")
        assert list(participant.task(task_id)["decisions"]) == CHECKPOINTS
        assert len(participant.task(task_id)["messages"]) == 8
        participant.call("POST", f"/tasks/{task_id}/finish", {"reason": "submitted"})
        assert participant.step == survey_step
        participant.survey(task_id, [25, 0, 50, 75, 25, 0])
        assert participant.task(task_id)["survey"]["rawScore"] == pytest.approx(175 / 6)

    assert participant.step == "feedback"
    participant.call("POST", "/feedback", {"interfaceComments": "", "studyComments": "Synthetic note"})
    assert participant.step == "completion"
    assert participant.state["feedback"]["version"] == "provisional-feedback-v1"
    participant.fail("POST", "/feedback", {"interfaceComments": "", "studyComments": ""}, 409, "INVALID_STEP")


def test_automatic_routing_applies_recommendation_without_choices(dev_client):
    participant = Participant(dev_client, 1)  # task-1 = A automatic
    participant.through_practice()
    participant.start()
    participant.fail("POST", "/tasks/task-1/messages", {"text": "hi"}, 409, "MODEL_REQUIRED")
    participant.fail("POST", "/tasks/task-1/routing/initial", {"model": "large"}, 409, "INVALID_ROUTING_PHASE")
    decision = participant.route("task-1")
    assert decision["initialModel"] is None
    assert decision["recommendedModel"] == decision["finalModel"] == "small"
    assert decision["reason"].startswith("Simulated recommendation")
    participant.call("POST", "/tasks/task-1/routing/recommendation", {"checkpoint": "Venue"})
    assert participant.task()["decisions"]["Venue"] == decision  # repeat changes nothing
    participant.fail("POST", "/tasks/task-1/routing/confirm", {"model": "large"}, 409, "INVALID_ROUTING_PHASE")


@pytest.mark.parametrize("final", ["large", "small"])  # retain vs change
def test_override_locks_initial_choice_before_reveal(dev_client, clock, final):
    participant = Participant(dev_client, 3)  # task-1 = A override
    participant.through_practice()
    participant.start()
    venue = participant.task()["decisions"]["Venue"]
    assert venue["phase"] == "choose" and venue["recommendedModel"] is None
    participant.fail("POST", "/tasks/task-1/routing/recommendation", {}, 409, "INVALID_ROUTING_PHASE")
    participant.fail("POST", "/tasks/task-1/routing/initial", {"model": "medium"}, 400, "INVALID_MODEL")
    participant.call("POST", "/tasks/task-1/routing/initial", {"model": "large"})
    assert participant.task()["decisions"]["Venue"]["recommendedModel"] is None  # still hidden
    participant.fail("POST", "/tasks/task-1/messages", {"text": "hi"}, 409, "MODEL_REQUIRED")
    clock.advance(1000)
    participant.call("POST", "/tasks/task-1/routing/recommendation", {})
    clock.advance(1000)
    participant.call("POST", "/tasks/task-1/routing/confirm", {"model": final})
    decision = participant.task()["decisions"]["Venue"]
    assert (decision["initialModel"], decision["recommendedModel"], decision["finalModel"]) == ("large", "small", final)
    assert decision["initialLockedAt"] < decision["recommendationShownAt"] < decision["finalCommittedAt"]
    participant.fail("POST", "/tasks/task-1/routing/confirm", {"model": "large"}, 409, "INVALID_ROUTING_PHASE")
    participant.call("POST", "/tasks/task-1/messages", {"text": "Compare venues"})
    assert participant.task()["messages"][-1]["model"] == final


def test_stale_checkpoint_requests_are_rejected(dev_client):
    participant = Participant(dev_client, 1)
    participant.through_practice()
    participant.start()
    participant.route("task-1")
    participant.call("POST", "/tasks/task-1/checkpoint/advance", {"checkpoint": "Venue"})
    before = participant.task()
    participant.fail("POST", "/tasks/task-1/messages", {"checkpoint": "Venue", "text": "late"}, 409, "STALE_OPERATION")
    participant.fail("PUT", "/tasks/task-1/plan", {"checkpoint": "Venue", "plan": PLAN_A}, 409, "STALE_OPERATION")
    assert participant.client.get(f"/api/sessions/{participant.sid}").json()["tasks"]["task-1"] == before


def test_invalid_and_incomplete_plans_can_be_submitted(dev_client):
    participant = Participant(dev_client, 1)
    participant.through_practice()
    participant.start()
    participant.call("PUT", "/tasks/task-1/plan", {"plan": PLAN_A})
    participant.call("POST", "/tasks/task-1/finish", {"reason": "submitted"})
    task = participant.task("task-1")
    assert task["status"] == "submitted" and task["totalCostCents"] == 30000
    assert task["constraints"] == {"budget": True, "capacity": True, "dietary": False, "accessibility": True}
    assert list(task["decisions"]) == ["Venue"]  # unvisited checkpoints are not fabricated
    participant.fail("POST", "/tasks/task-1/finish", {}, 409, "NO_ACTIVE_TASK")
    participant.fail("PUT", "/tasks/task-1/plan", {"plan": PLAN_A}, 409, "NO_ACTIVE_TASK")


def test_late_planning_request_expires_task_and_preserves_work(dev_client, clock):
    participant = Participant(dev_client, 1)
    participant.through_practice()
    participant.start()
    deadline = participant.task()["deadline"]
    participant.route("task-1")
    participant.call("PUT", "/tasks/task-1/plan", {"plan": PLAN_A})
    clock.advance(EXPERIMENTAL_TASK_MS)
    data = participant.fail("PUT", "/tasks/task-1/plan", {"plan": {"venue": None, "catering": None, "supplies": []}},
                            409, "TASK_EXPIRED")
    task = data["state"]["tasks"]["task-1"]
    assert data["state"]["step"] == "tlx-1"
    assert task["status"] == "timed-out" and task["endedAt"] == deadline
    assert task["plan"] == PLAN_A  # the late update was not applied
    stored = participant.client.get(f"/api/sessions/{participant.sid}").json()
    assert stored == data["state"]
    participant.fail("POST", "/tasks/task-1/messages", {"text": "late"}, 409, "NO_ACTIVE_TASK")


def test_finish_after_deadline_records_timeout_at_deadline(dev_client, clock):
    participant = Participant(dev_client, 2)
    participant.through_practice()
    participant.start()
    deadline = participant.task()["deadline"]
    clock.advance(1000)
    participant.call("POST", "/tasks/task-1/begin")  # repeated begin keeps the deadline
    assert participant.task()["deadline"] == deadline
    clock.advance(EXPERIMENTAL_TASK_MS + 30_000)
    participant.call("POST", "/tasks/task-1/finish", {"reason": "submitted"})
    task = participant.task("task-1")
    assert task["status"] == "timed-out" and task["endedAt"] == deadline
    assert participant.step == "tlx-1"


def test_explicit_timeout_goes_to_the_linked_survey(dev_client):
    participant = Participant(dev_client, 4)
    participant.through_practice()
    participant.start()
    participant.call("POST", "/tasks/task-1/finish", {"reason": "timed-out"})
    assert participant.task("task-1")["status"] == "timed-out" and participant.step == "tlx-1"


def test_survey_validation_and_scoring(dev_client):
    participant = Participant(dev_client, 1)
    participant.through_practice()
    participant.start()
    participant.fail("PUT", "/surveys/task-1", {"answers": {"effort": 25}}, 400, "INVALID_SURVEY")  # task active
    participant.call("POST", "/tasks/task-1/finish", {"reason": "submitted"})
    metadata = participant.task("task-1")["survey"]["metadata"]
    assert metadata["version"] == "provisional-adapted-nasa-tlx-5-v2" and metadata["increment"] == 25
    participant.fail("PUT", "/surveys/task-1", {"answers": {"effort": 30}}, 400, "INVALID_SURVEY")
    participant.fail("PUT", "/surveys/task-1", {"answers": {"effort": 125}}, 400, "INVALID_SURVEY")
    participant.fail("PUT", "/surveys/task-1", {"answers": {"mood": 25}}, 400, "INVALID_SURVEY")
    participant.fail("PUT", "/surveys/task-1", {"answers": {"effort": True}}, 400, "INVALID_REQUEST")
    participant.call("PUT", "/surveys/task-1", {"answers": {"mentalDemand": 25, "effort": 50}})
    participant.fail("POST", "/surveys/task-1/submit", None, 400, "INCOMPLETE_SURVEY")
    assert participant.task("task-1")["survey"]["answers"] == {"mentalDemand": 25, "effort": 50}
    participant.call("PUT", "/surveys/task-1", {"answers": {
        "physicalDemand": 100, "temporalDemand": 100, "performance": 100, "frustration": 100,
        "mentalDemand": 100, "effort": 100}})
    participant.call("POST", "/surveys/task-1/submit")
    assert participant.task("task-1")["survey"]["rawScore"] == 100
    assert participant.step == "task-2"
    participant.fail("POST", "/surveys/task-1/submit", None, 400, "INCOMPLETE_SURVEY")  # duplicate
