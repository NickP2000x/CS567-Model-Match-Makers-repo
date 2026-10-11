"""Study constants and provisional materials, kept identical to the frontend mock.

`fixtures/catalog.json` and `fixtures/definitions.json` are exported from the frontend
sources with `node backend/scripts/export_fixtures.mjs`; rerun it after changing those files.
"""

import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DEFINITIONS = json.loads((FIXTURES / "definitions.json").read_text(encoding="utf-8"))

# Paper Table 1 sequences: (task-1 assignment, task-2 assignment).
SEQUENCES = {
    1: ({"scenarioId": "A", "condition": "automatic"}, {"scenarioId": "B", "condition": "override"}),
    2: ({"scenarioId": "B", "condition": "automatic"}, {"scenarioId": "A", "condition": "override"}),
    3: ({"scenarioId": "A", "condition": "override"}, {"scenarioId": "B", "condition": "automatic"}),
    4: ({"scenarioId": "B", "condition": "override"}, {"scenarioId": "A", "condition": "automatic"}),
}
CHECKPOINTS = ["Venue", "Catering", "Supplies", "Final constraint check"]
TASK_IDS = ("practice", "task-1", "task-2")
SURVEY_DIMENSIONS = ["mentalDemand", "physicalDemand", "temporalDemand", "performance", "effort", "frustration"]
EXPERIMENTAL_TASK_MS = 15 * 60 * 1000

SURVEY_DEFINITIONS = DEFINITIONS["surveys"]["definitions"]
CURRENT_SURVEY = SURVEY_DEFINITIONS[DEFINITIONS["surveys"]["current"]]
PREPARATIONS = DEFINITIONS["preparations"]
FEEDBACK_VERSION = DEFINITIONS["feedback"]["version"]
RECOMMENDATIONS = DEFINITIONS["recommendations"]


def canned_response(model: str, checkpoint: str) -> str:
    if model == "small":
        return f"[Simulated small model] {checkpoint}: inspect the catalog details before choosing."
    return (f"[Simulated large model] {checkpoint}: compare alternatives and review budget, "
            "capacity, dietary coverage, and wheelchair access.")
