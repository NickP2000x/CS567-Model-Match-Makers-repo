"""Read-only catalog queries and the four constraint checks (ported from the frontend mock)."""

import json
import sqlite3

from .errors import ApiError

SUMMARY_FIELDS = ("id", "scenarioId", "category", "name", "summary", "priceCents")


def get_scenario(connection: sqlite3.Connection, scenario_id: str) -> dict:
    row = connection.execute("SELECT data FROM catalog_scenarios WHERE id = ?", (scenario_id,)).fetchone()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Scenario not found.")
    return json.loads(row["data"])


def search(connection: sqlite3.Connection, scenario_id: str, query: str = "", category: str | None = None) -> list[dict]:
    """Summaries only; hidden capacity/dietary/access details come from inspection."""
    get_scenario(connection, scenario_id)
    rows = connection.execute(
        "SELECT data FROM catalog_items WHERE scenario_id = ? AND (? IS NULL OR category = ?) ORDER BY position",
        (scenario_id, category, category)).fetchall()
    needle = query.lower()
    items = [json.loads(row["data"]) for row in rows]
    return [{field: item[field] for field in SUMMARY_FIELDS}
            for item in items if needle in f"{item['name']} {item['summary']}".lower()]


def get_item(connection: sqlite3.Connection, item_id: str) -> dict | None:
    row = connection.execute("SELECT data FROM catalog_items WHERE id = ?", (item_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def evaluate(connection: sqlite3.Connection, task: dict) -> None:
    """Recompute total cost and the four constraints for a task's current plan."""
    plan = task["plan"]
    chosen = [item_id for item_id in [plan["venue"], plan["catering"], *plan["supplies"]] if item_id]
    items = [item for item in (get_item(connection, item_id) for item_id in chosen) if item]
    venue = next((item for item in items if item["category"] == "venue"), None)
    food = next((item for item in items if item["category"] == "catering"), None)
    requirements = get_scenario(connection, task["scenarioId"])["requirements"]
    total = sum(item["priceCents"] for item in items)
    task["totalCostCents"] = total
    task["constraints"] = {
        "budget": total <= requirements["budgetCents"],
        "capacity": (venue or {}).get("capacity", 0) >= requirements["attendees"],
        "dietary": (food or {}).get("servings", 0) >= requirements["attendees"]
        and all(need in (food or {}).get("dietaryCoverage", []) for need in requirements["dietaryNeeds"]),
        "accessibility": not requirements["wheelchairRequired"] or (venue or {}).get("wheelchairAccessible") is True,
    }
