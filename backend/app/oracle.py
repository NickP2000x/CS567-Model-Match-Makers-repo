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
    "Supplies": ("budget", "capacity", "dietary", "accessibility"),
    "Final constraint check": ("budget", "capacity", "dietary", "accessibility"),
}
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
    def __init__(self, size: str, calls: list[CallRecord]):
        super().__init__(f"{size} model call failed")
        self.size, self.calls = size, calls


@dataclass
class Proposal:
    plan: dict | None
    passed: bool
    calls: list[CallRecord] = field(default_factory=list)


def oracle_prompt(scenario: dict, checkpoint: str, plan: dict) -> str:
    requirements = scenario["requirements"]
    return (
        f"You are planning an event: {scenario['title']}. Requirements: {requirements['attendees']} guests; "
        f"budget {requirements['budgetCents'] / 100:.2f} USD for venue, catering, and supplies together; "
        f"dietary needs: {', '.join(requirements['dietaryNeeds'])}; wheelchair access "
        f"{'required' if requirements['wheelchairRequired'] else 'not required'}.\n"
        f"Current stage: {checkpoint}. Current plan (item ids): {json.dumps(plan)}.\n"
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


def propose(client: ChatClient, connection: sqlite3.Connection, scenario: dict, checkpoint: str,
            plan: dict, max_steps: int) -> Proposal:
    """Bounded tool loop that ends when the model calls submit_plan (or runs out of steps)."""
    tools = CatalogTools(connection, scenario["id"])
    messages = [{"role": "system", "content": oracle_prompt(scenario, checkpoint, plan)},
                {"role": "user", "content": "Propose and submit the plan for this stage."}]
    calls: list[CallRecord] = []
    for step in range(1, max_steps + 2):
        offered = [SUBMIT_TOOL] if step == max_steps + 1 else [*TOOLS, SUBMIT_TOOL]
        started = time.monotonic()
        try:
            reply = client.chat(messages, offered)
        except ModelError as error:
            calls.append(CallRecord(step, False, int((time.monotonic() - started) * 1000), error=str(error)))
            raise OracleFailed(client.size, calls) from None
        calls.append(CallRecord(step, True, int((time.monotonic() - started) * 1000),
                                reply.prompt_tokens, reply.completion_tokens, [c.name for c in reply.tool_calls]))
        if not reply.tool_calls:
            break
        messages.append({"role": "assistant", "content": reply.content or "", "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
            for c in reply.tool_calls]})
        for tool_call in reply.tool_calls:
            if tool_call.name == "submit_plan":
                try:
                    args = json.loads(tool_call.arguments or "{}")
                    submitted = {"venue": args.get("venue"), "catering": args.get("catering"),
                                 "supplies": list(args.get("supplies") or [])}
                except (ValueError, TypeError, AttributeError):
                    submitted = None
                return Proposal(submitted, stage_passes(connection, scenario["id"], checkpoint, submitted), calls)
            result = tools.run(tool_call.name, tool_call.arguments)
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})
    return Proposal(None, False, calls)


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
