from app.definitions import EXPERIMENTAL_TASK_MS
from tests.conftest import Participant

PLAN = {"venue": "A-venue-good", "catering": None, "supplies": []}


def submitted_task_1(client, clock):
    participant = Participant(client, 1)
    participant.through_practice()
    participant.start()
    participant.route("task-1")
    participant.call("PUT", "/tasks/task-1/plan", {"plan": PLAN})
    clock.advance(60_000)
    participant.call("POST", "/tasks/task-1/finish", {"reason": "submitted"})
    assert participant.step == "tlx-1"
    return participant


def test_back_to_task_keeps_work_and_the_original_deadline(dev_client, clock):
    participant = submitted_task_1(dev_client, clock)
    before = participant.task("task-1")
    clock.advance(5_000)
    participant.call("PUT", "/surveys/task-1", {"answers": {"effort": 50}})  # partial ratings are kept
    participant.call("POST", "/tasks/task-1/reopen")
    task = participant.task("task-1")
    assert participant.step == "task-1" and task["status"] == "active" and task["endedAt"] is None
    assert task["deadline"] == before["deadline"] and task["plan"] == PLAN
    assert task["decisions"] == before["decisions"]
    assert task["reopens"] == [{"endedAt": before["endedAt"], "reopenedAt": clock.now}]
    participant.call("PUT", "/tasks/task-1/plan", {"plan": dict(PLAN, catering="A-food-good")})  # editable again
    participant.call("POST", "/tasks/task-1/finish", {"reason": "submitted"})
    assert participant.step == "tlx-1" and participant.task("task-1")["survey"]["answers"] == {"effort": 50}
    participant.call("POST", "/tasks/task-1/reopen")  # more than once is allowed
    assert len(participant.task("task-1")["reopens"]) == 2


def test_cannot_reopen_after_time_runs_out(dev_client, clock):
    participant = submitted_task_1(dev_client, clock)
    clock.advance(EXPERIMENTAL_TASK_MS)
    before = participant.state
    participant.fail("POST", "/tasks/task-1/reopen", None, 409, "TASK_EXPIRED")
    assert dev_client.get(f"/api/sessions/{participant.sid}").json() == before


def test_rated_timed_out_and_practice_tasks_cannot_reopen(dev_client, clock):
    participant = submitted_task_1(dev_client, clock)
    participant.survey("task-1", [25, 0, 50, 75, 25, 0])
    participant.fail("POST", "/tasks/task-1/reopen", None, 409, "INVALID_STEP")  # already rated
    participant.start()
    participant.call("POST", "/tasks/task-2/finish", {"reason": "timed-out"})
    participant.fail("POST", "/tasks/task-2/reopen", None, 409, "INVALID_STEP")  # timed out
    participant.fail("POST", "/tasks/practice/reopen", None, 400, "INVALID_REQUEST")
