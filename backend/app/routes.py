"""HTTP routes for the experiment service (docs/experiment-api-http-draft.md).

Every successful mutation returns the participant-visible study state.
"""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, StrictBool, StrictFloat, StrictInt

from . import catalog, study
from .agent import AgentContext, AgentFailed
from .errors import ApiError
from .store import Store

router = APIRouter(prefix="/api")

TaskId = Literal["practice", "task-1", "task-2"]
SurveyTaskId = Literal["task-1", "task-2"]
PreparationId = Literal["before-start", "practice", "task-1", "task-2"]
ScenarioId = Literal["practice", "A", "B"]
Category = Literal["venue", "catering", "supplies"]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SequenceBody(Body):
    sequenceId: int | None = None


class ConsentBody(Body):
    accepted: StrictBool


class DemographicsBody(Body):
    age: int
    gender: str
    priorLlmUsage: str


class PreparationBody(Body):
    acknowledgedIds: list[str]


class CheckpointBody(Body):
    # The checkpoint the client is acting on; a mismatch returns STALE_OPERATION.
    checkpoint: str | None = None


class InspectBody(CheckpointBody):
    itemId: str


class Plan(Body):
    venue: str | None
    catering: str | None
    supplies: list[str]


class PlanBody(CheckpointBody):
    plan: Plan


class ModelBody(CheckpointBody):
    model: str


class MessageBody(CheckpointBody):
    text: str


class FinishBody(Body):
    reason: Literal["submitted", "timed-out"] = "submitted"


class SurveyBody(Body):
    answers: dict[str, StrictInt | StrictFloat]


class FeedbackBody(Body):
    interfaceComments: str
    studyComments: str


def store(request: Request) -> Store:
    return request.app.state.store


def development_sequence(request: Request, body: SequenceBody | None) -> int | None:
    sequence_id = body.sequenceId if body else None
    if sequence_id is not None and not request.app.state.settings.dev_controls:
        raise ApiError(400, "INVALID_REQUEST", "Sequence selection is only available in development.")
    return sequence_id


# --- Catalog ----------------------------------------------------------------------

@router.get("/scenarios/{scenario_id}")
def get_scenario(request: Request, scenario_id: ScenarioId) -> dict:
    return store(request).read(lambda connection: catalog.get_scenario(connection, scenario_id))


@router.get("/scenarios/{scenario_id}/catalog")
def search_catalog(request: Request, scenario_id: ScenarioId, query: str = "", category: Category | None = None) -> list[dict]:
    return store(request).read(lambda connection: catalog.search(connection, scenario_id, query, category))


# --- Sessions and introduction ----------------------------------------------------

@router.post("/sessions", status_code=201)
def create_session(request: Request, body: SequenceBody | None = None) -> dict:
    return store(request).create_session(development_sequence(request, body))


@router.get("/sessions/{sid}")
def get_session(request: Request, sid: str) -> dict:
    return store(request).get_state(sid)


@router.post("/sessions/{sid}/reset", status_code=201)
def reset_session(request: Request, sid: str, body: SequenceBody | None = None) -> dict:
    """Development only: start a fresh session (new sessionId), leaving the old one untouched."""
    if not request.app.state.settings.dev_controls:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    previous = store(request).get_state(sid)
    return store(request).create_session((body.sequenceId if body else None) or previous["sequenceId"])


def mutate(request: Request, sid: str, operation) -> dict:
    return store(request).mutate(sid, operation)[1]


@router.post("/sessions/{sid}/consent")
def record_consent(request: Request, sid: str, body: ConsentBody) -> dict:
    return mutate(request, sid, lambda c, s, now: study.record_consent(s, body.accepted))


@router.post("/sessions/{sid}/demographics")
def save_demographics(request: Request, sid: str, body: DemographicsBody) -> dict:
    return mutate(request, sid, lambda c, s, now: study.save_demographics(s, body.age, body.gender, body.priorLlmUsage))


@router.post("/sessions/{sid}/preparations/{preparation_id}")
def confirm_preparation(request: Request, sid: str, preparation_id: PreparationId, body: PreparationBody) -> dict:
    return mutate(request, sid, lambda c, s, now: study.confirm_preparation(s, preparation_id, body.acknowledgedIds, now))


@router.post("/sessions/{sid}/tutorial/complete")
def complete_tutorial(request: Request, sid: str) -> dict:
    return mutate(request, sid, lambda c, s, now: study.complete_tutorial(s))


# --- Planning tasks ---------------------------------------------------------------

@router.post("/sessions/{sid}/tasks/{task_id}/begin")
def begin_task(request: Request, sid: str, task_id: TaskId) -> dict:
    return mutate(request, sid, lambda c, s, now: study.begin_task(s, task_id, now))


@router.post("/sessions/{sid}/tasks/{task_id}/inspect")
def inspect_item(request: Request, sid: str, task_id: TaskId, body: InspectBody) -> dict:
    def operation(connection, state, now):
        task = study.planning_task(connection, state, task_id, body.checkpoint, now)
        return study.inspect_item(connection, task, body.itemId)
    item, state = store(request).mutate(sid, operation)
    return {"item": item, "state": state}


@router.put("/sessions/{sid}/tasks/{task_id}/plan")
def update_plan(request: Request, sid: str, task_id: TaskId, body: PlanBody) -> dict:
    def operation(connection, state, now):
        task = study.planning_task(connection, state, task_id, body.checkpoint, now)
        study.update_plan(connection, task, body.plan.model_dump())
    return mutate(request, sid, operation)


@router.post("/sessions/{sid}/tasks/{task_id}/routing/initial")
def lock_initial_choice(request: Request, sid: str, task_id: TaskId, body: ModelBody) -> dict:
    return mutate(request, sid, lambda c, s, now: study.lock_initial_choice(
        study.planning_task(c, s, task_id, body.checkpoint, now), body.model, now))


@router.post("/sessions/{sid}/tasks/{task_id}/routing/recommendation")
def request_recommendation(request: Request, sid: str, task_id: TaskId, body: CheckpointBody | None = None) -> dict:
    checkpoint = body.checkpoint if body else None
    return mutate(request, sid, lambda c, s, now: study.request_recommendation(
        study.planning_task(c, s, task_id, checkpoint, now), now))


@router.post("/sessions/{sid}/tasks/{task_id}/routing/confirm")
def confirm_model(request: Request, sid: str, task_id: TaskId, body: ModelBody) -> dict:
    return mutate(request, sid, lambda c, s, now: study.confirm_model(
        study.planning_task(c, s, task_id, body.checkpoint, now), body.model, now))


@router.post("/sessions/{sid}/tasks/{task_id}/messages")
def send_message(request: Request, sid: str, task_id: TaskId, body: MessageBody) -> dict:
    """Validate under the lock, call the agent without holding it, then save the reply only
    if the task is still active at the same checkpoint (late replies are discarded)."""
    current = store(request)
    agent = request.app.state.agent

    def prepare(connection, state, now):
        task = study.planning_task(connection, state, task_id, body.checkpoint, now)
        model = study.message_model(task, body.text)
        scenario = catalog.get_scenario(connection, task["scenarioId"])
        context = AgentContext(scenario, task["checkpoint"], task["plan"], study.message_history(task), body.text)
        return model, context, now

    (model, context, sent_at), _ = current.mutate(sid, prepare)
    provider, model_name = agent.describe(model)

    def record(calls, shown):
        current.record_model_calls(sid, task_id, context.checkpoint, model, provider, model_name, calls, shown)

    try:
        reply = current.read(lambda connection: agent.reply(model, context, connection))
    except AgentFailed as failure:
        record(failure.calls, shown=False)
        raise ApiError(502, "PROVIDER_ERROR", "The AI assistant is unavailable right now. Please try again.") from None

    def commit(connection, state, now):
        task = study.planning_task(connection, state, task_id, context.checkpoint, now)
        study.append_exchange(task, body.text, reply.text, model, reply.simulated, sent_at, now)

    try:
        _, state = current.mutate(sid, commit)
    except ApiError:
        record(reply.calls, shown=False)
        raise
    record(reply.calls, shown=True)
    return state


@router.post("/sessions/{sid}/tasks/{task_id}/checkpoint/advance")
def advance_checkpoint(request: Request, sid: str, task_id: TaskId, body: CheckpointBody | None = None) -> dict:
    checkpoint = body.checkpoint if body else None
    return mutate(request, sid, lambda c, s, now: study.advance_checkpoint(
        study.planning_task(c, s, task_id, checkpoint, now), now))


@router.post("/sessions/{sid}/tasks/{task_id}/finish")
def finish_task(request: Request, sid: str, task_id: TaskId, body: FinishBody | None = None) -> dict:
    reason = body.reason if body else "submitted"
    return mutate(request, sid, lambda c, s, now: study.finish_task(c, s, task_id, reason, now))


# --- Surveys and feedback ---------------------------------------------------------

@router.put("/sessions/{sid}/surveys/{task_id}")
def save_survey_answers(request: Request, sid: str, task_id: SurveyTaskId, body: SurveyBody) -> dict:
    return mutate(request, sid, lambda c, s, now: study.save_survey_answers(s, task_id, body.answers))


@router.post("/sessions/{sid}/surveys/{task_id}/submit")
def submit_survey(request: Request, sid: str, task_id: SurveyTaskId) -> dict:
    return mutate(request, sid, lambda c, s, now: study.submit_survey(s, task_id, now))


@router.post("/sessions/{sid}/feedback")
def submit_feedback(request: Request, sid: str, body: FeedbackBody) -> dict:
    return mutate(request, sid, lambda c, s, now: study.submit_feedback(
        s, body.interfaceComments, body.studyComments, now))
