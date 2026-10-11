import json
import sqlite3

import pytest

from app import db
from app.agent import EMPTY_ANSWER, AgentContext, AgentFailed, CatalogTools, ModelAgent, system_prompt
from app.catalog import get_scenario
from app.models import ModelError
from tests.fakes import ScriptedClient, answer, tool


@pytest.fixture
def connection(tmp_path):
    path = tmp_path / "agent.sqlite3"
    db.init_db(path)
    conn = db.connect(path)
    yield conn
    conn.close()


def context(connection, scenario="A", checkpoint="Venue", plan=None, history=None, text="Which venue fits?"):
    return AgentContext(get_scenario(connection, scenario), checkpoint,
                        plan or {"venue": None, "catering": None, "supplies": []}, history or [], text)


def agent_with(small_replies, large_replies=(), max_steps=4):
    clients = {"small": ScriptedClient("small", small_replies), "large": ScriptedClient("large", list(large_replies))}
    return ModelAgent(clients, max_steps), clients


def tool_results(client):
    """Tool messages the agent sent back to the model in its last request."""
    return [json.loads(m["content"]) for m in client.requests[-1][0] if m["role"] == "tool"]


def test_agent_uses_tools_then_answers_with_locked_model(connection):
    agent, clients = agent_with([], [
        tool("search_catalog", {"category": "venue"}),
        tool("inspect_item", {"item_id": "A-venue-good"}),
        tool("check_plan", {"venue": "A-venue-good", "catering": "A-food-good", "supplies": ["A-supplies-good"]}),
        answer("Willow Conference Hall fits all four requirements."),
    ])
    reply = agent.reply("large", context(connection), connection)
    assert reply.text == "Willow Conference Hall fits all four requirements." and reply.simulated is False
    assert clients["small"].requests == []  # the stage's locked model only
    assert [call.tools for call in reply.calls] == [["search_catalog"], ["inspect_item"], ["check_plan"], []]
    assert all(call.ok for call in reply.calls) and reply.calls[0].prompt_tokens == 20
    search, item, check = tool_results(clients["large"])
    assert [entry["id"] for entry in search] == ["A-venue-good", "A-venue-capacity", "A-venue-access"]
    assert "capacity" not in search[0]  # search returns summaries only
    assert item["capacity"] == 40 and item["wheelchairAccessible"] is True
    assert check == {"totalCostCents": 80000, "allConstraintsMet": True,
                     "constraints": {"budget": True, "capacity": True, "dietary": True, "accessibility": True}}


def test_failed_check_is_reported_so_the_model_can_revise(connection):
    agent, clients = agent_with([
        tool("check_plan", {"venue": "A-venue-access", "catering": None, "supplies": []}),
        answer("Maple Suite is not accessible; choose Willow Conference Hall instead."),
    ])
    agent.reply("small", context(connection), connection)
    (result,) = tool_results(clients["small"])
    assert result["allConstraintsMet"] is False and result["constraints"]["accessibility"] is False


def test_tool_errors_are_returned_to_the_model_not_raised(connection):
    agent, clients = agent_with([
        tool("inspect_item", {"item_id": "B-venue-good"}, "c1"),
        tool("check_plan", {"venue": "A-food-good"}, "c2"),
        tool("search_catalog", "not json", "c3"),
        tool("delete_everything", {}, "c4"),
        answer("Here is what I found."),
    ], max_steps=5)
    reply = agent.reply("small", context(connection), connection)
    errors = [result["error"] for result in tool_results(clients["small"])]
    assert errors == ["Item not found in this event's catalog.", "A-food-good is not a venue item in this event's catalog.",
                      "Arguments must be a JSON object.", "Unknown tool delete_everything."]
    assert reply.text == "Here is what I found."


def test_loop_is_bounded_and_forces_a_final_answer(connection):
    agent, clients = agent_with([tool("search_catalog", {}) for _ in range(3)] + [answer("Final answer.")], max_steps=3)
    reply = agent.reply("small", context(connection), connection)
    assert reply.text == "Final answer."
    assert len(clients["small"].requests) == 4
    assert clients["small"].requests[-1][1] is None  # last call offers no tools
    assert [call.step for call in reply.calls] == [1, 2, 3, 4]


def test_empty_answers_get_a_safe_fallback(connection):
    agent, _ = agent_with([answer("   ")])
    assert agent.reply("small", context(connection), connection).text == EMPTY_ANSWER


def test_provider_failure_keeps_call_records(connection):
    agent, _ = agent_with([tool("search_catalog", {}), ModelError("openai returned HTTP 500")])
    with pytest.raises(AgentFailed) as failure:
        agent.reply("small", context(connection), connection)
    assert [(call.step, call.ok, call.error) for call in failure.value.calls] == [
        (1, True, None), (2, False, "openai returned HTTP 500")]


def test_prompt_contains_requirements_stage_plan_and_history(connection):
    plan = {"venue": "B-venue-good", "catering": None, "supplies": []}
    history = [{"role": "user", "content": f"q{i}"} for i in range(20)]
    agent, clients = agent_with([answer("ok")])
    agent.reply("small", context(connection, "B", "Catering", plan, history, "And catering?"), connection)
    messages = clients["small"].requests[0][0]
    prompt = messages[0]["content"]
    for expected in ("60 guests", "1400.00 USD", "vegan, nut-free", "wheelchair access required",
                     "Current stage: Catering", '"venue": "B-venue-good"', "You cannot change the plan"):
        assert expected in prompt, expected
    assert [m["content"] for m in messages[1:-1]] == [f"q{i}" for i in range(8, 20)]  # last 12 history messages
    assert messages[-1] == {"role": "user", "content": "And catering?"}
    assert system_prompt(context(connection, "practice")).count("15 guests") == 1


def test_catalog_tools_never_change_stored_state(connection):
    before = connection.execute("SELECT COUNT(*), SUM(LENGTH(data)) FROM catalog_items").fetchone()
    tools = CatalogTools(connection, "A")
    tools.run("check_plan", json.dumps({"venue": "A-venue-good", "catering": "A-food-good", "supplies": ["A-supplies-cost"]}))
    assert tools.run("check_plan", json.dumps({"supplies": "A-supplies-good"}))["error"].startswith("supplies must")
    assert tuple(connection.execute("SELECT COUNT(*), SUM(LENGTH(data)) FROM catalog_items").fetchone()) == tuple(before)
