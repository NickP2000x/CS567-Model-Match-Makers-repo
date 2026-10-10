"""Planning agent (#36): a bounded tool-calling loop over the study catalog.

The agent answers the participant within the current checkpoint using the stage's
locked model. It can search, inspect, and check plans, but never changes the plan:
the participant adds or removes items (provisional decision, pending researcher review).
"""

import json
import sqlite3
import time
from dataclasses import dataclass, field

from . import catalog
from .definitions import canned_response
from .models import ChatClient, ModelError

MAX_HISTORY_MESSAGES = 12
EMPTY_ANSWER = "Sorry, I could not produce an answer. Please try rephrasing your question."

TOOLS = [
    {"type": "function", "function": {
        "name": "search_catalog",
        "description": "Search this event's catalog. Returns item summaries (id, name, category, price in cents).",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Words to match in item names or summaries; empty for all."},
            "category": {"type": "string", "enum": ["venue", "catering", "supplies"]},
        }},
    }},
    {"type": "function", "function": {
        "name": "inspect_item",
        "description": "Get full details for one catalog item: capacity, wheelchair access, servings, dietary coverage.",
        "parameters": {"type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"]},
    }},
    {"type": "function", "function": {
        "name": "check_plan",
        "description": "Check a candidate plan against budget, capacity, dietary coverage, and wheelchair access.",
        "parameters": {"type": "object", "properties": {
            "venue": {"type": ["string", "null"]},
            "catering": {"type": ["string", "null"]},
            "supplies": {"type": "array", "items": {"type": "string"}},
        }},
    }},
]


@dataclass
class AgentContext:
    scenario: dict
    checkpoint: str
    plan: dict
    history: list[dict]
    text: str


@dataclass
class CallRecord:
    step: int
    ok: bool
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    tools: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class AgentReply:
    text: str
    simulated: bool
    calls: list[CallRecord]


class AgentFailed(Exception):
    def __init__(self, calls: list[CallRecord]):
        super().__init__("model call failed")
        self.calls = calls


def system_prompt(context: AgentContext) -> str:
    requirements = context.scenario["requirements"]
    return (
        "You are the AI planning assistant in a research study about event planning. "
        f"Event: {context.scenario['title']}. Requirements: {requirements['attendees']} guests; "
        f"budget {requirements['budgetCents'] / 100:.2f} USD for venue, catering, and supplies together; "
        f"dietary needs: {', '.join(requirements['dietaryNeeds'])}; wheelchair access "
        f"{'required' if requirements['wheelchairRequired'] else 'not required'}.\n"
        f"Current stage: {context.checkpoint} (stages: Venue, Catering, Supplies, Final constraint check). "
        "Focus on this stage.\n"
        f"Participant's current plan (item ids): {json.dumps(context.plan)}.\n"
        "Use the tools for facts; never invent items, prices, or details. Before recommending a "
        "combination, call check_plan and revise if a constraint fails. You cannot change the plan: "
        "tell the participant which items to add or remove. Answer in under 120 words, "
        "using item names rather than ids. Only discuss this event-planning task."
    )


class CatalogTools:
    def __init__(self, connection: sqlite3.Connection, scenario_id: str):
        self.connection, self.scenario_id = connection, scenario_id

    def run(self, name: str, arguments: str) -> dict | list:
        try:
            args = json.loads(arguments or "{}")
            if not isinstance(args, dict):
                raise ValueError
        except ValueError:
            return {"error": "Arguments must be a JSON object."}
        if name == "search_catalog":
            category = args.get("category")
            if category not in (None, "venue", "catering", "supplies"):
                return {"error": "Unknown category."}
            return catalog.search(self.connection, self.scenario_id, str(args.get("query") or ""), category)
        if name == "inspect_item":
            item = catalog.get_item(self.connection, str(args.get("item_id", "")))
            if item is None or item["scenarioId"] != self.scenario_id:
                return {"error": "Item not found in this event's catalog."}
            return item
        if name == "check_plan":
            plan = {"venue": args.get("venue"), "catering": args.get("catering"), "supplies": args.get("supplies") or []}
            if not isinstance(plan["supplies"], list):
                return {"error": "supplies must be a list of item ids."}
            for category, item_id in [("venue", plan["venue"]), ("catering", plan["catering"])] + [
                    ("supplies", supply) for supply in plan["supplies"]]:
                item = catalog.get_item(self.connection, str(item_id)) if item_id else None
                if item_id and (item is None or item["scenarioId"] != self.scenario_id or item["category"] != category):
                    return {"error": f"{item_id} is not a {category} item in this event's catalog."}
            task = {"scenarioId": self.scenario_id, "plan": plan}
            catalog.evaluate(self.connection, task)
            return {"totalCostCents": task["totalCostCents"], "constraints": task["constraints"],
                    "allConstraintsMet": all(task["constraints"].values())}
        return {"error": f"Unknown tool {name}."}


class MockAgent:
    """The frontend mock's canned replies; no model calls."""

    simulated = True

    def describe(self, model: str) -> tuple[str, str]:
        return "mock", model

    def reply(self, model: str, context: AgentContext, connection: sqlite3.Connection) -> AgentReply:
        return AgentReply(canned_response(model, context.checkpoint), True, [])


class ModelAgent:
    simulated = False

    def __init__(self, clients: dict[str, ChatClient], max_steps: int):
        self.clients, self.max_steps = clients, max_steps

    def describe(self, model: str) -> tuple[str, str]:
        client = self.clients[model]
        return client.provider, client.model

    def reply(self, model: str, context: AgentContext, connection: sqlite3.Connection) -> AgentReply:
        client = self.clients[model]  # locked stage model; never changes inside the loop
        tools = CatalogTools(connection, context.scenario["id"])
        messages = [{"role": "system", "content": system_prompt(context)},
                    *context.history[-MAX_HISTORY_MESSAGES:], {"role": "user", "content": context.text}]
        calls: list[CallRecord] = []

        def call(step: int, with_tools: bool):
            started = time.monotonic()
            try:
                reply = client.chat(messages, TOOLS if with_tools else None)
            except ModelError as error:
                calls.append(CallRecord(step, False, int((time.monotonic() - started) * 1000), error=str(error)))
                raise AgentFailed(calls) from None
            calls.append(CallRecord(step, True, int((time.monotonic() - started) * 1000),
                                    reply.prompt_tokens, reply.completion_tokens, [c.name for c in reply.tool_calls]))
            return reply

        for step in range(1, self.max_steps + 1):
            reply = call(step, with_tools=True)
            if not reply.tool_calls:
                return AgentReply((reply.content or "").strip() or EMPTY_ANSWER, False, calls)
            messages.append({"role": "assistant", "content": reply.content or "", "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                for c in reply.tool_calls]})
            for tool_call in reply.tool_calls:
                result = tools.run(tool_call.name, tool_call.arguments)
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})
        # Tool limit reached: one last call without tools forces a plain answer.
        messages.append({"role": "system", "content": "Tool limit reached. Answer the participant now without tools."})
        reply = call(self.max_steps + 1, with_tools=False)
        return AgentReply((reply.content or "").strip() or EMPTY_ANSWER, False, calls)
