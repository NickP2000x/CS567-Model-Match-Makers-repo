"""Offline paired-output oracle (#40): `python -m app.oracle` (MODEL_MODE=real).

For each applied checkpoint recommendation, both models get the same frozen context (the
scenario, stage, and plan stored in `routing_decisions`) and propose a plan. A deterministic
check decides whether each proposal passes the stage. Label: `small` if the small model
passes, `large` if only the large model passes, `neither` otherwise (the neither case and
any reliance formula are researcher decisions). Results and their model usage are stored
separately and never shown to participants or written into session state.
"""

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import catalog, db
from .agent import TOOLS, CallRecord, CatalogTools
from .config import get_settings
from .models import ChatClient, ModelError, build_clients
from .store import Store

# Provisional pass rule: constraints that must hold once each stage is planned.
STAGE_CHECKS = {
    "Venue": ("capacity", "accessibility"),
    "Catering": ("capacity", "accessibility", "dietary"),
    "Supplies": ("budget", "capacity", "dietary", "accessibility", "supplies"),
    "Final constraint check": ("budget", "capacity", "dietary", "accessibility", "supplies"),
}
PROPOSAL_PROTOCOL_VERSION = "bounded-stage-proposal-v6-structured-completion"
SUBMIT_TOOL = {"type": "function", "function": {
    "name": "submit_plan",
    "description": "Submit your final complete plan (item ids). Call exactly once when done.",
    "parameters": {"type": "object", "properties": {
        "venue": {"type": ["string", "null"]},
        "catering": {"type": ["string", "null"]},
        "supplies": {"type": "array", "items": {"type": "string"}},
    }, "required": ["venue", "catering", "supplies"]},
}}


class OracleFailed(Exception):
    def __init__(self, size: str, calls: list[CallRecord], trace: list[dict] | None = None,
                 request_overrides: list[dict] | None = None):
        super().__init__(f"{size} model call failed")
        self.size, self.calls = size, calls
        self.trace = trace or []
        self.request_overrides = request_overrides or []


@dataclass
class Proposal:
    plan: dict | None
    passed: bool
    calls: list[CallRecord] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    request_overrides: list[dict] = field(default_factory=list)


def oracle_prompt(scenario: dict, checkpoint: str, plan: dict) -> str:
    requirements = scenario["requirements"]
    return (
        f"You are planning an event: {scenario['title']}. Requirements: {requirements['attendees']} guests; "
        f"budget {requirements['budgetCents'] / 100:.2f} USD for venue, catering, and supplies together; "
        f"dietary needs: {', '.join(requirements['dietaryNeeds'])}; wheelchair access "
        f"{'required' if requirements['wheelchairRequired'] else 'not required'}; "
        f"required supplies: {', '.join(requirements['requiredSupplies'])}.\n"
        f"Current stage: {checkpoint}. Current plan (item ids): {json.dumps(plan, sort_keys=True)}.\n"
        f"Checkpoint acceptance checks: {', '.join(STAGE_CHECKS[checkpoint])}. "
        "Focus on this stage and earlier stages; later-stage choices may remain null or empty "
        "when they are not needed by these acceptance checks.\n"
        "Use the catalog tools to choose items for this stage and any earlier stage that is still "
        "missing or wrong, check the plan, then call submit_plan once with the complete plan."
    )


def label(small_passed: bool, large_passed: bool) -> str:
    if small_passed:
        return "small"
    return "large" if large_passed else "neither"


def stage_passes(connection: sqlite3.Connection, scenario_id: str, checkpoint: str, plan: dict | None) -> bool:
    if not plan:
        return False
    result = CatalogTools(connection, scenario_id).run("check_plan", json.dumps(plan))
    if not isinstance(result, dict) or "error" in result:
        return False
    return all(result["constraints"][name] for name in STAGE_CHECKS[checkpoint])


def parsed_plan(value) -> dict | None:
    """Normalize nullable fields, but never invent IDs or repair a model's choices."""
    if not isinstance(value, dict):
        return None
    supplies = value.get("supplies")
    plan = {"venue": value.get("venue"), "catering": value.get("catering"),
            "supplies": [] if supplies is None else supplies}
    if any(item is not None and not isinstance(item, str) for item in (plan["venue"], plan["catering"])):
        return None
    if not isinstance(plan["supplies"], list) or any(not isinstance(item, str) for item in plan["supplies"]):
        return None
    if len(set(plan["supplies"])) != len(plan["supplies"]):
        return None
    return plan


def final_plan_messages(scenario, checkpoint, plan, messages):
    """Fresh terminal request using only facts the model actually retrieved."""
    items, requests, checks = {}, {}, []
    for message in messages:
        for call in message.get("tool_calls", []):
            requests[call["id"]] = call["function"]
        if message["role"] != "tool":
            continue
        data = json.loads(message["content"])
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and "id" in item:
                items.setdefault(item["id"], {}).update(item)
        if isinstance(data, dict) and "constraints" in data:
            request = requests.get(message.get("tool_call_id"), {})
            checks.append({"plan": json.loads(request.get("arguments", "{}")), "result": data})
    facts = {"event": scenario, "checkpoint": checkpoint, "acceptance_checks": STAGE_CHECKS[checkpoint],
             "current_plan": plan, "observed_catalog_items": list(items.values()), "checked_candidates": checks}
    return [{"role": "system", "content":
        "Choose an event plan from the supplied fixed facts. Return exactly one JSON object with keys "
        "venue (item ID or null), catering (item ID or null), and supplies (array of item IDs). "
        "No prose or code fences. Use only observed IDs or current-plan IDs. Satisfy the listed "
        "checkpoint acceptance checks; later-stage choices may remain null/empty. Do not request further information."},
        {"role": "user", "content": json.dumps(facts, sort_keys=True)}]


def propose(client: ChatClient, connection: sqlite3.Connection, scenario: dict, checkpoint: str,
            plan: dict, max_steps: int, question: str | None = None) -> Proposal:
    """Bounded tool loop plus one strict JSON finalization call if not submitted earlier."""
    tools = CatalogTools(connection, scenario["id"])
    messages = [{"role": "system", "content": oracle_prompt(scenario, checkpoint, plan)},
                {"role": "user", "content": (question + "\n" if question else "")
                 + "Propose and submit the plan for this stage."}]
    calls: list[CallRecord] = []
    request_overrides: list[dict] = []
    finalize_next = False
    for step in range(1, max_steps + 2):
        final = finalize_next or step == max_steps + 1
        offered = None if final else [*TOOLS, SUBMIT_TOOL]
        request_messages = messages
        if final:
            request_messages = final_plan_messages(scenario, checkpoint, plan, messages)
            request_overrides.append({"step": step, "messages": request_messages, "format": "stage-plan-json-v1"})
        started = time.monotonic()
        try:
            reply = client.chat(request_messages, offered)
        except ModelError as error:
            calls.append(CallRecord(step, False, int((time.monotonic() - started) * 1000), error=str(error)))
            raise OracleFailed(client.size, calls, messages, request_overrides) from None
        calls.append(CallRecord(step, True, int((time.monotonic() - started) * 1000),
                                reply.prompt_tokens, reply.completion_tokens, [c.name for c in reply.tool_calls]))
        if final or not reply.tool_calls:
            messages.append(reply.assistant_message())
            try:
                submitted = parsed_plan(json.loads(reply.content or ""))
            except ValueError:
                submitted = None
            if submitted is not None or final:
                return Proposal(submitted, stage_passes(connection, scenario["id"], checkpoint, submitted), calls, messages, request_overrides)
            # A natural-language draft is not a scoreable plan. Use one remaining
            # call for structured collection instead of silently treating it as a
            # capability failure; never exceed max_steps + 1 total calls.
            finalize_next = True
            continue
        messages.append(reply.assistant_message())
        for tool_call in reply.tool_calls:
            if tool_call.name not in {t["function"]["name"] for t in offered}:
                messages.append({"role": "tool", "tool_call_id": tool_call.id,
                                 "content": json.dumps({"error": "Tool not available in this call."})})
                continue
            if tool_call.name == "submit_plan":
                try:
                    submitted = parsed_plan(json.loads(tool_call.arguments or "{}"))
                except ValueError:
                    submitted = None
                return Proposal(submitted, stage_passes(connection, scenario["id"], checkpoint, submitted), calls, messages, request_overrides)
            result = tools.run(tool_call.name, tool_call.arguments)
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})
    return Proposal(None, False, calls, messages, request_overrides)


def record_oracle_calls(store: Store, clients: dict[str, ChatClient], context: dict,
                        calls_by_size: dict[str, list[CallRecord]]) -> None:
    for size, calls in calls_by_size.items():
        store.record_model_calls(context["session_id"], context["task_id"], context["checkpoint"], size,
                                 clients[size].provider, clients[size].model, calls, shown=False, purpose="oracle")


def evaluate_pending(store: Store, clients: dict[str, ChatClient], max_steps: int,
                     limit: int | None = None) -> list[dict]:
    """Evaluate applied recommendations that have no oracle result yet. Failed checkpoints are
    left pending (their calls are recorded) so a later run can retry them."""
    rows = store.read(lambda connection: connection.execute(
        "SELECT r.* FROM routing_decisions r LEFT JOIN oracle_results o ON o.routing_id = r.id"
        " WHERE r.applied = 1 AND o.id IS NULL ORDER BY r.id" + (f" LIMIT {int(limit)}" if limit else "")).fetchall())
    results = []
    for row in rows:
        context = dict(row)
        plan = json.loads(context["plan"])
        proposals: dict[str, Proposal] = {}
        try:
            for size in ("small", "large"):
                proposals[size] = store.read(lambda connection: propose(
                    clients[size], connection, catalog.get_scenario(connection, context["scenario_id"]),
                    context["checkpoint"], plan, max_steps))
        except OracleFailed as failure:
            calls_by_size = {size: proposal.calls for size, proposal in proposals.items()}
            calls_by_size[failure.size] = failure.calls
            record_oracle_calls(store, clients, context, calls_by_size)
            results.append({"routing_id": context["id"], "error": str(failure)})
            continue
        record_oracle_calls(store, clients, context, {size: p.calls for size, p in proposals.items()})
        outcome = {"routing_id": context["id"], "session_id": context["session_id"], "task_id": context["task_id"],
                   "checkpoint": context["checkpoint"], "small_passed": proposals["small"].passed,
                   "large_passed": proposals["large"].passed,
                   "label": label(proposals["small"].passed, proposals["large"].passed)}
        with db.transaction(store.path) as connection:
            connection.execute(
                "INSERT INTO oracle_results (routing_id, session_id, task_id, checkpoint, small_plan, small_passed,"
                " large_plan, large_passed, label, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (context["id"], context["session_id"], context["task_id"], context["checkpoint"],
                 json.dumps(proposals["small"].plan), int(outcome["small_passed"]),
                 json.dumps(proposals["large"].plan), int(outcome["large_passed"]), outcome["label"], store.clock()))
        results.append(outcome)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the paired-output oracle on recorded checkpoints.")
    parser.add_argument("--limit", type=int, help="evaluate at most this many checkpoints")
    args = parser.parse_args(argv)
    settings = get_settings()
    if settings.model_mode != "real":
        print("The oracle calls both models: set MODEL_MODE=real (and the model settings) in backend/.env.")
        return 2
    store = Store(Path(settings.resolved_database_path))
    results = evaluate_pending(store, build_clients(settings), settings.agent_max_steps, args.limit)
    for result in results:
        if "error" in result:
            print(f"routing #{result['routing_id']}: FAILED ({result['error']}); left pending")
        else:
            print(f"routing #{result['routing_id']} {result['task_id']} {result['checkpoint']}: "
                  f"small {'pass' if result['small_passed'] else 'fail'}, "
                  f"large {'pass' if result['large_passed'] else 'fail'} -> {result['label']}")
    print(f"{sum('error' not in r for r in results)} evaluated, {sum('error' in r for r in results)} failed.")
    return 1 if any("error" in r for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
