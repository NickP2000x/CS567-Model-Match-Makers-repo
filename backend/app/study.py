"""Study rules, ported one-to-one from frontend/src/services/mockExperiment.ts.

Functions mutate a session's state dict (the frontend `StudyState` shape) and raise
`ApiError` with the mock's codes and messages. Callers persist the state afterwards.
"""

import copy
import math
import sqlite3

from . import catalog
from .definitions import (
    CHECKPOINTS, CURRENT_SURVEY, EXPERIMENTAL_TASK_MS, FEEDBACK_VERSION, PREPARATIONS,
    RECOMMENDATIONS, SEQUENCES, SURVEY_DIMENSIONS, canned_response,
)
from .errors import ApiError

PLANNING_STEPS = ("practice", "task-1", "task-2")
SURVEY_STEP = {"task-1": "tlx-1", "task-2": "tlx-2"}


class TaskExpired(Exception):
    """Raised after a late planning request has ended the task; the ended state is saved."""


def invalid_step(message: str) -> ApiError:
    return ApiError(409, "INVALID_STEP", message)


def routing_phase(message: str) -> ApiError:
    return ApiError(409, "INVALID_ROUTING_PHASE", message)


def new_state(session_id: str, participant_id: str, sequence_id: int) -> dict:
    if sequence_id not in SEQUENCES:
        raise ApiError(400, "INVALID_SEQUENCE", "Choose sequence 1–4.")
    return {
        "sessionId": session_id, "participantId": participant_id, "sequenceId": sequence_id,
        "assignments": copy.deepcopy(list(SEQUENCES[sequence_id])), "step": "consent",
        "consent": None, "demographics": None, "tasks": {}, "preparations": {}, "feedback": None,
        "simulated": True,
    }


# --- Introduction -----------------------------------------------------------------

def record_consent(state: dict, accepted: bool) -> None:
    if state["step"] != "consent":
        raise invalid_step("Consent is the first step.")
    state["consent"] = accepted
    if accepted:
        state["step"] = "demographics"


def save_demographics(state: dict, age: int, gender: str, prior_llm_usage: str) -> None:
    if state["step"] != "demographics":
        raise invalid_step("Complete consent first.")
    if age < 0 or not gender.strip() or not prior_llm_usage.strip():
        raise ApiError(400, "INVALID_DEMOGRAPHICS", "Enter synthetic age, gender, and prior LLM usage.")
    state["demographics"] = {"age": age, "gender": gender, "priorLlmUsage": prior_llm_usage}
    state["step"] = "tutorial"


def confirm_preparation(state: dict, preparation_id: str, acknowledged_ids: list[str], now: int) -> None:
    definition = PREPARATIONS[preparation_id]
    expected_step = "tutorial" if preparation_id == "before-start" else preparation_id
    if state["step"] != expected_step:
        raise invalid_step("This preparation is not current.")
    if preparation_id in state["preparations"]:
        return  # Keep the original acknowledgement and time on duplicates.
    statement_ids = [statement["id"] for statement in definition["statements"]]
    if sorted(acknowledged_ids) != sorted(statement_ids) or len(set(acknowledged_ids)) != len(acknowledged_ids):
        raise ApiError(400, "INVALID_PREPARATION", "Acknowledge each instruction before continuing.")
    state["preparations"][preparation_id] = {
        **copy.deepcopy(definition), "acknowledgedIds": list(acknowledged_ids), "confirmedAt": now,
    }


def complete_tutorial(state: dict) -> None:
    if state["step"] != "tutorial":
        raise invalid_step("Complete demographics first.")
    if "before-start" not in state["preparations"]:
        raise ApiError(409, "INVALID_PREPARATION", "Acknowledge the before-start instructions first.")
    state["step"] = "practice"


# --- Tasks ------------------------------------------------------------------------

def new_decision(task: dict, now: int) -> dict:
    practice = task["condition"] == "practice"
    return {
        "phase": "committed" if practice else "choose" if task["condition"] == "override" else "awaiting-recommendation",
        "initialModel": None, "recommendedModel": None, "finalModel": "small" if practice else None,
        "reason": None, "shownAt": now, "initialLockedAt": None, "recommendationShownAt": None,
        "finalCommittedAt": now if practice else None,
    }


def begin_task(state: dict, task_id: str, now: int) -> None:
    if state["step"] not in PLANNING_STEPS:
        raise invalid_step("Reach a planning step first.")
    if state["step"] != task_id:
        raise invalid_step("The planning step is no longer current.")
    if task_id not in state["preparations"]:
        raise ApiError(409, "INVALID_PREPARATION", "Start the task from its preparation screen.")
    if task_id in state["tasks"]:
        return  # Repeated requirements-visible events never restart the deadline.
    practice = task_id == "practice"
    assignment = ({"scenarioId": "practice", "condition": "practice"} if practice
                  else state["assignments"][0 if task_id == "task-1" else 1])
    task = {
        "id": task_id, **assignment, "excludedFromResults": practice, "status": "active",
        "startedAt": now, "deadline": None if practice else now + EXPERIMENTAL_TASK_MS, "endedAt": None,
        "checkpoint": "Venue", "decisions": {}, "messages": [], "inspectedItems": [],
        "plan": {"venue": None, "catering": None, "supplies": []}, "totalCostCents": 0,
        "constraints": {"budget": True, "capacity": False, "dietary": False, "accessibility": False},
        "survey": {"answers": {}, "metadata": None if practice else copy.deepcopy(CURRENT_SURVEY),
                   "rawScore": None, "submittedAt": None},
    }
    task["decisions"]["Venue"] = new_decision(task, now)
    state["tasks"][task_id] = task


def end_task(connection: sqlite3.Connection, state: dict, task: dict, reason: str, at: int) -> None:
    expired = task["deadline"] is not None and at >= task["deadline"]
    task["status"] = "timed-out" if expired else reason
    task["endedAt"] = task["deadline"] if expired else at
    catalog.evaluate(connection, task)
    state["step"] = "task-1" if task["id"] == "practice" else SURVEY_STEP[task["id"]]


def active_task(state: dict, task_id: str) -> dict:
    task = state["tasks"].get(task_id)
    if task is None:
        raise ApiError(409, "NO_ACTIVE_TASK", "Start an active planning task first.")
    if state["step"] != task_id or task["status"] != "active":
        raise ApiError(409, "NO_ACTIVE_TASK", "The original task has ended.")
    return task


def planning_task(connection: sqlite3.Connection, state: dict, task_id: str,
                  checkpoint: str | None, now: int) -> dict:
    """Guard every planning request: active task, same checkpoint, deadline not passed."""
    task = active_task(state, task_id)
    if checkpoint is not None and checkpoint != task["checkpoint"]:
        raise ApiError(409, "STALE_OPERATION", "The original checkpoint has ended.")
    if task["deadline"] is not None and now >= task["deadline"]:
        end_task(connection, state, task, "timed-out", task["deadline"])
        raise TaskExpired()
    return task


def finish_task(connection: sqlite3.Connection, state: dict, task_id: str, reason: str, now: int) -> None:
    end_task(connection, state, active_task(state, task_id), reason, now)


def inspect_item(connection: sqlite3.Connection, task: dict, item_id: str) -> dict:
    item = catalog.get_item(connection, item_id)
    if item is None or item["scenarioId"] != task["scenarioId"]:
        raise ApiError(404, "NOT_FOUND", "Item not found in this task.")
    if item_id not in task["inspectedItems"]:
        task["inspectedItems"].append(item_id)
    return item


def update_plan(connection: sqlite3.Connection, task: dict, plan: dict) -> None:
    entries = [("venue", plan["venue"]), ("catering", plan["catering"])]
    entries += [("supplies", item_id) for item_id in plan["supplies"]]
    for category, item_id in entries:
        item = catalog.get_item(connection, item_id) if item_id else None
        if item_id and (item is None or item["scenarioId"] != task["scenarioId"] or item["category"] != category):
            raise ApiError(400, "INVALID_PLAN", "Plan items must belong to the task and correct category.")
    task["plan"] = {"venue": plan["venue"], "catering": plan["catering"],
                    "supplies": list(dict.fromkeys(plan["supplies"]))}
    catalog.evaluate(connection, task)


# --- Routing and agent ------------------------------------------------------------

def check_model(model: str) -> None:
    if model not in ("small", "large"):
        raise ApiError(400, "INVALID_MODEL", "Choose small or large.")


def lock_initial_choice(task: dict, model: str, now: int) -> None:
    check_model(model)
    decision = task["decisions"][task["checkpoint"]]
    if task["condition"] != "override" or decision["phase"] != "choose":
        raise routing_phase("Initial choice is unavailable.")
    decision.update(initialModel=model, initialLockedAt=now, phase="locked")


def request_recommendation(task: dict, now: int) -> None:
    decision = task["decisions"][task["checkpoint"]]
    if task["condition"] == "practice" or (task["condition"] == "override" and decision["phase"] == "choose"):
        raise routing_phase("Lock the independent initial choice before revealing the recommendation.")
    if decision["recommendedModel"]:
        return  # Repeated requests return the same recommendation and timestamps.
    recommendation = RECOMMENDATIONS[task["checkpoint"]]
    decision.update(recommendedModel=recommendation["model"], reason=recommendation["reason"],
                    recommendationShownAt=now)
    if task["condition"] == "automatic":
        decision.update(phase="committed", finalModel=recommendation["model"], finalCommittedAt=now)
    else:
        decision["phase"] = "recommended"


def confirm_model(task: dict, model: str, now: int) -> None:
    check_model(model)
    decision = task["decisions"][task["checkpoint"]]
    if task["condition"] != "override" or decision["phase"] != "recommended":
        raise routing_phase("Model choice is unavailable or already fixed.")
    decision.update(finalModel=model, finalCommittedAt=now, phase="committed")


def send_message(task: dict, text: str, now: int) -> None:
    model = task["decisions"][task["checkpoint"]]["finalModel"]
    if not model:
        raise ApiError(409, "MODEL_REQUIRED", "Complete routing before agent work.")
    if not text.strip():
        raise ApiError(400, "EMPTY_MESSAGE", "Enter a message.")
    index = len(task["messages"])
    base = {"checkpoint": task["checkpoint"], "createdAt": now}
    task["messages"] += [
        {"id": f"{task['id']}-message-{index}", "role": "user", "text": text.strip(),
         "model": None, "simulated": False, **base},
        {"id": f"{task['id']}-message-{index + 1}", "role": "assistant",
         "text": canned_response(model, task["checkpoint"]), "model": model, "simulated": True, **base},
    ]


def advance_checkpoint(task: dict, now: int) -> None:
    if not task["decisions"][task["checkpoint"]]["finalModel"]:
        raise ApiError(409, "MODEL_REQUIRED", "Complete routing before advancing.")
    position = CHECKPOINTS.index(task["checkpoint"])
    if position == len(CHECKPOINTS) - 1:
        raise ApiError(409, "FINAL_CHECKPOINT", "Submit the current plan.")
    task["checkpoint"] = CHECKPOINTS[position + 1]
    task["decisions"][task["checkpoint"]] = new_decision(task, now)


# --- Workload survey and feedback -------------------------------------------------

def is_survey_response(value: object, metadata: dict) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
            and metadata["min"] <= value <= metadata["max"]
            and (value - metadata["min"]) % metadata["increment"] == 0)


def workload_mean(answers: dict, metadata: dict) -> float | None:
    """Unweighted mean of six correctly oriented common-scale values (higher = more workload)."""
    total = 0.0
    for dimension in SURVEY_DIMENSIONS:
        value = answers.get(dimension)
        if value is None or not is_survey_response(value, metadata):
            return None
        common = 100 * (value - metadata["min"]) / (metadata["max"] - metadata["min"])
        oriented = metadata["items"][dimension]["orientation"] == "higher-is-more-workload"
        total += common if oriented else 100 - common
    return total / len(SURVEY_DIMENSIONS)


def survey_task(state: dict, task_id: str) -> dict | None:
    task = state["tasks"].get(task_id)
    if (task is None or task_id == "practice" or task["status"] == "active" or not task["survey"]["metadata"]
            or task["survey"]["submittedAt"] is not None or state["step"] != SURVEY_STEP.get(task_id)):
        return None
    return task


def save_survey_answers(state: dict, task_id: str, answers: dict) -> None:
    task = survey_task(state, task_id)
    if task is None:
        raise ApiError(400, "INVALID_SURVEY", "Survey is unavailable for this task.")
    metadata = task["survey"]["metadata"]
    for key, value in answers.items():
        if key not in SURVEY_DIMENSIONS or not is_survey_response(value, metadata):
            raise ApiError(400, "INVALID_SURVEY",
                           f"Choose a response from 0 to 100 in steps of {metadata['increment']}.")
    task["survey"]["answers"].update(answers)


def submit_survey(state: dict, task_id: str, now: int) -> None:
    task = survey_task(state, task_id)
    if task is None or any(dimension not in task["survey"]["answers"] for dimension in SURVEY_DIMENSIONS):
        raise ApiError(400, "INCOMPLETE_SURVEY", "Answer all six dimensions for the current task.")
    score = workload_mean(task["survey"]["answers"], task["survey"]["metadata"])
    if score is None:
        raise ApiError(400, "INVALID_SURVEY", "Choose a valid response for all six dimensions.")
    task["survey"].update(rawScore=score, submittedAt=now)
    state["step"] = "task-2" if task_id == "task-1" else "feedback"


def submit_feedback(state: dict, interface_comments: str, study_comments: str, now: int) -> None:
    if state["step"] != "feedback" or state["feedback"]:
        raise invalid_step("Feedback is unavailable at this step.")
    state["feedback"] = {"interfaceComments": interface_comments, "studyComments": study_comments,
                         "version": FEEDBACK_VERSION, "submittedAt": now}
    state["step"] = "completion"
