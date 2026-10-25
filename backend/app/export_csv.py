"""Read-only SQLite -> linked CSV export. Does not import application settings."""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .offline import BACKEND_DIR, new_run_directory, read_snapshot, write_csv, write_json

VERSION = "study-csv-v1"
DIMENSIONS = ("mentalDemand", "physicalDemand", "temporalDemand", "performance", "effort", "frustration")
RELATIONAL = ("routing_decisions", "model_calls", "oracle_results")
BASE_COLUMNS = {
    "sessions": ("session_id", "participant_id", "sequence_id", "development", "step", "consent",
        "created_at_ms", "updated_at_ms", "simulated", "router_simulated", "age", "gender", "prior_llm_usage",
        "feedback_interface_comments", "feedback_study_comments", "feedback_version", "feedback_submitted_at_ms",
        "demographics_json", "assignments_json", "feedback_json", "state_extra_json"),
    "preparations": ("session_id", "preparation_id", "version", "confirmed_at_ms", "acknowledged_ids_json", "statements_json", "preparation_json"),
    "tasks": ("session_id", "task_id", "scenario_id", "condition", "status", "practice", "excluded_from_results",
        "checkpoint", "started_at_ms", "deadline_ms", "ended_at_ms", "elapsed_seconds", "total_cost_cents",
        "constraint_budget", "constraint_capacity", "constraint_dietary", "constraint_accessibility",
        "constraints_satisfied", "all_four_met", "survey_raw_score", "survey_version", "survey_submitted_at_ms",
        *(f"survey_{k}" for k in DIMENSIONS), "plan_json", "constraints_json", "survey_metadata_json", "survey_answers_json", "task_extra_json"),
    "plan_items": ("session_id", "task_id", "category", "position", "item_id", "item_name", "catalog_price_cents"),
    "messages": ("session_id", "task_id", "position", "message_id", "role", "checkpoint", "model", "text", "created_at_ms", "simulated", "message_json"),
    "checkpoint_choices": ("session_id", "task_id", "checkpoint", "phase", "initial_model", "recommended_model", "final_model",
        "reason", "shown_at_ms", "initial_locked_at_ms", "recommendation_shown_at_ms", "final_committed_at_ms",
        "decision_total_ms", "initial_choice_ms", "post_recommendation_ms", "decision_json"),
    "survey_responses": ("session_id", "task_id", "dimension", "raw_value", "version", "orientation", "submitted_at_ms",
        "min", "max", "increment", "label", "question", "left_anchor", "right_anchor", "labels_json"),
    "task_reopens": ("session_id", "task_id", "position", "ended_at_ms", "reopened_at_ms"),
    "inspections": ("session_id", "task_id", "position", "item_id", "item_name"),
    "routing_decisions": ("id", "session_id", "task_id", "checkpoint", "router", "score", "threshold", "recommended", "ok", "error", "applied", "latency_ms", "created_at_ms"),
    "model_calls": ("id", "session_id", "task_id", "checkpoint", "purpose", "size", "provider", "model", "step", "ok", "error", "prompt_tokens", "completion_tokens", "latency_ms", "tools", "shown", "created_at_ms"),
    "oracle_results": ("id", "routing_id", "session_id", "task_id", "checkpoint", "small_plan", "small_passed", "large_plan", "large_passed", "label", "created_at_ms"),
    "catalog_items": ("item_id", "scenario_id", "category", "item_name", "catalog_price_cents", "data_json"),
}
for _name, _fields in list(BASE_COLUMNS.items()):
    if _name != "catalog_items":
        _shared = ["participant_id", "sequence_id", "development"]
        if "task_id" in _fields:
            _shared += ["practice", "excluded_from_results"]
        BASE_COLUMNS[_name] = tuple(dict.fromkeys([*_fields, *_shared]))


def mapping(value) -> dict:
    return value if isinstance(value, dict) else {}


def difference(end, start, divisor=1):
    if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (end, start)):
        return (end - start) / divisor
    return None


def flatten_snapshot(connection: sqlite3.Connection, study_only=False) -> tuple[dict, dict]:
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "sessions" not in tables:
        raise ValueError("The selected database has no sessions table.")
    data = {name: [] for name in BASE_COLUMNS}
    warnings = []
    counts = {}
    source_columns = {}

    def rows(table):
        if table not in tables:
            warnings.append(f"Missing optional source table: {table}")
            counts[table] = None
            source_columns[table] = None
            return []
        source_columns[table] = [r[1] for r in connection.execute(f'PRAGMA table_info("{table}")')]
        result = [dict(r) for r in connection.execute(f'SELECT * FROM "{table}"')]
        counts[table] = len(result)
        return result

    items = {}
    for row in rows("catalog_items"):
        item = mapping(json.loads(row.get("data") or "{}"))
        items[row["id"]] = item
        data["catalog_items"].append({"item_id": row["id"], "scenario_id": row.get("scenario_id"),
            "category": row.get("category"), "item_name": item.get("name"),
            "catalog_price_cents": item.get("priceCents"), "data_json": item})

    selected = {}
    selected_tasks = set()
    for row in rows("sessions"):
        state = json.loads(row["state"])
        if not isinstance(state, dict):
            raise ValueError("Session state must be a JSON object.")
        development = row.get("development")
        if study_only and development != 0:
            continue  # Unknown development status is not silently classified as study data.
        sid = row["id"]
        base = {"session_id": sid, "participant_id": row.get("participant_id"),
                "sequence_id": row.get("sequence_id"), "development": development}
        selected[sid] = base
        demographics = mapping(state.get("demographics"))
        feedback = mapping(state.get("feedback"))
        data["sessions"].append({**base, "step": state.get("step"), "consent": state.get("consent"),
            "created_at_ms": row.get("created_at"), "updated_at_ms": row.get("updated_at"),
            "simulated": state.get("simulated"), "router_simulated": state.get("routerSimulated"),
            "age": demographics.get("age"), "gender": demographics.get("gender"),
            "prior_llm_usage": demographics.get("priorLlmUsage"), "demographics_json": state.get("demographics"),
            "assignments_json": state.get("assignments"),
            "feedback_interface_comments": feedback.get("interfaceComments"),
            "feedback_study_comments": feedback.get("studyComments"), "feedback_version": feedback.get("version"),
            "feedback_json": state.get("feedback"),
            "feedback_submitted_at_ms": feedback.get("submittedAt"),
            "state_extra_json": {k: v for k, v in state.items() if k not in {
                "tasks", "preparations", "demographics", "feedback", "assignments"}}})
        for pid, prep in mapping(state.get("preparations")).items():
            if study_only and pid == "practice":
                continue
            if prep is None:
                continue
            if not isinstance(prep, dict):
                raise ValueError("Preparation records must be objects.")
            data["preparations"].append({**base, "preparation_id": pid, "version": prep.get("version"),
                "confirmed_at_ms": prep.get("confirmedAt"), "acknowledged_ids_json": prep.get("acknowledgedIds"),
                "statements_json": prep.get("statements"), "preparation_json": prep})
        for tid, task in mapping(state.get("tasks")).items():
            if task is None:
                continue
            if not isinstance(task, dict):
                raise ValueError("Task records must be objects.")
            practice = tid == "practice"
            if study_only and (practice or task.get("excludedFromResults") is True):
                continue
            selected_tasks.add((sid, tid))
            linked = {**base, "task_id": tid, "practice": practice,
                      "excluded_from_results": task.get("excludedFromResults")}
            plan = mapping(task.get("plan"))
            survey = mapping(task.get("survey"))
            answers = mapping(survey.get("answers"))
            metadata = mapping(survey.get("metadata"))
            constraints = mapping(task.get("constraints"))
            required = ("budget", "capacity", "dietary", "accessibility")
            complete = all(isinstance(constraints.get(key), bool) for key in required)
            data["tasks"].append({**linked, "scenario_id": task.get("scenarioId"), "condition": task.get("condition"),
                "status": task.get("status"), "checkpoint": task.get("checkpoint"),
                "started_at_ms": task.get("startedAt"), "deadline_ms": task.get("deadline"),
                "ended_at_ms": task.get("endedAt"),
                "elapsed_seconds": difference(task.get("endedAt"), task.get("startedAt"), 1000),
                "total_cost_cents": task.get("totalCostCents"), "plan_json": task.get("plan"),
                "constraints_json": task.get("constraints"),
                **{f"constraint_{k}": constraints.get(k) for k in required},
                "constraints_satisfied": sum(constraints[k] for k in required) if complete else None,
                "all_four_met": all(constraints[k] for k in required) if complete else None,
                "survey_raw_score": survey.get("rawScore"), "survey_version": metadata.get("version"),
                "survey_submitted_at_ms": survey.get("submittedAt"), "survey_metadata_json": survey.get("metadata"),
                "survey_answers_json": survey.get("answers"), **{f"survey_{k}": answers.get(k) for k in DIMENSIONS}})
            data["tasks"][-1]["task_extra_json"] = {k: v for k, v in task.items() if k not in {
                "plan", "constraints", "messages", "survey", "decisions", "reopens", "inspectedItems"}}
            chosen = [("venue", 0, plan.get("venue")), ("catering", 0, plan.get("catering"))]
            chosen += [("supplies", index, item) for index, item in enumerate(plan.get("supplies") or [])]
            for category, position, item_id in chosen:
                if item_id is not None:
                    item = items.get(item_id, {})
                    data["plan_items"].append({**linked, "category": category, "position": position,
                        "item_id": item_id, "item_name": item.get("name"), "catalog_price_cents": item.get("priceCents")})
            for index, message in enumerate(task.get("messages") or []):
                data["messages"].append({**linked, "position": index, "message_id": message.get("id"),
                    "role": message.get("role"), "checkpoint": message.get("checkpoint"), "model": message.get("model"),
                    "text": message.get("text"), "simulated": message.get("simulated"), "created_at_ms": message.get("createdAt"),
                    "message_json": message})
            for checkpoint, decision in mapping(task.get("decisions")).items():
                if decision is None:
                    continue
                if not isinstance(decision, dict):
                    raise ValueError("Checkpoint decision records must be objects.")
                data["checkpoint_choices"].append({**linked, "checkpoint": checkpoint, "decision_json": decision,
                    **{key: decision.get(source) for key, source in {
                        "phase": "phase", "initial_model": "initialModel", "recommended_model": "recommendedModel",
                        "final_model": "finalModel", "reason": "reason", "shown_at_ms": "shownAt",
                        "initial_locked_at_ms": "initialLockedAt", "recommendation_shown_at_ms": "recommendationShownAt",
                        "final_committed_at_ms": "finalCommittedAt"}.items()},
                    "decision_total_ms": difference(decision.get("finalCommittedAt"), decision.get("shownAt")),
                    "initial_choice_ms": difference(decision.get("initialLockedAt"), decision.get("shownAt")),
                    "post_recommendation_ms": difference(decision.get("finalCommittedAt"), decision.get("recommendationShownAt"))})
            for dimension, value in answers.items():
                item = mapping(mapping(metadata.get("items")).get(dimension))
                data["survey_responses"].append({**linked, "dimension": dimension, "raw_value": value,
                    "version": metadata.get("version"), "submitted_at_ms": survey.get("submittedAt"),
                    **{key: metadata.get(key) for key in ("min", "max", "increment")},
                    **{key: item.get(source) for key, source in {"label": "label", "question": "question",
                        "left_anchor": "leftAnchor", "right_anchor": "rightAnchor", "orientation": "orientation",
                        "labels_json": "labels"}.items()}})
            for index, reopen in enumerate(task.get("reopens") or []):
                data["task_reopens"].append({**linked, "position": index,
                    "ended_at_ms": reopen.get("endedAt"), "reopened_at_ms": reopen.get("reopenedAt")})
            for index, item_id in enumerate(task.get("inspectedItems") or []):
                data["inspections"].append({**linked, "position": index, "item_id": item_id,
                    "item_name": items.get(item_id, {}).get("name")})

    for table in RELATIONAL:
        source = rows(table)
        orphan_count = 0
        for row in source:
            sid, tid = row.get("session_id"), row.get("task_id")
            if study_only and (sid not in selected or (sid, tid) not in selected_tasks):
                continue
            normalized = {("created_at_ms" if k == "created_at" else k): v for k, v in row.items()}
            if sid not in selected:
                orphan_count += 1
            data[table].append({**selected.get(sid, {}), **normalized, "practice": tid == "practice"})
        if orphan_count:
            warnings.append(f"{table}: retained {orphan_count} rows without a matching session.")
        if table == "model_calls" and table in tables and "purpose" not in {
                row[1] for row in connection.execute('PRAGMA table_info("model_calls")')}:
            warnings.append("model_calls.purpose is absent; usage purpose is unknown, not inferred.")
    # Timestamp companions are derived display values; raw milliseconds remain unchanged.
    for dataset in data.values():
        for row in dataset:
            for key, value in list(row.items()):
                if key.endswith("_ms") and ("_at_" in key or key == "deadline_ms"):
                    try:
                        row[key[:-3] + "_utc"] = datetime.fromtimestamp(value / 1000, timezone.utc).isoformat() if value is not None else None
                    except (TypeError, ValueError, OverflowError, OSError):
                        row[key[:-3] + "_utc"] = None
    return data, {"source_counts": counts, "source_columns": source_columns, "warnings": warnings}


def field_description(name):
    explicit = {
        "decision_total_ms": "finalCommittedAt - shownAt; null if either is absent",
        "initial_choice_ms": "initialLockedAt - shownAt; null if either is absent",
        "post_recommendation_ms": "finalCommittedAt - recommendationShownAt; null if either is absent",
        "elapsed_seconds": "endedAt - startedAt, divided by 1000; null for an unfinished task",
        "purpose": "recorded participant/oracle purpose; null for earlier unknown schema",
        "raw_value": "stored workload response; not reversed or rescored",
        "survey_raw_score": "stored workload mean; not recomputed",
    }
    if name in explicit:
        return explicit[name]
    if name.endswith("_ms"):
        return "milliseconds since Unix epoch" if "_at_" in name or name == "deadline_ms" else "duration in milliseconds"
    if name.endswith("_utc"):
        return "derived ISO-8601 UTC display timestamp; raw epoch milliseconds are retained"
    if name.endswith("_cents"):
        return "integer USD cents; catalog_price_cents is the current catalog, not a frozen historical quote"
    if name.endswith("_json"):
        return "JSON preserving source structure/values"
    return "recorded source value or explicit session/task linkage; see dataset notes"


def export_database(database: Path, output: Path, study_only=False) -> Path:
    with read_snapshot(database) as connection:
        data, info = flatten_snapshot(connection, study_only)
        versions = dict(connection.execute("SELECT key,value FROM meta")) if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'").fetchone() else {}
    destination = new_run_directory(output, "export")
    write_json(destination / "manifest.json", {"version": VERSION, "status": "in_progress"})
    columns = {}
    for name, rows in data.items():
        fields = BASE_COLUMNS[name]
        timestamps = [key[:-3] + "_utc" for key in fields if key.endswith("_ms") and ("_at_" in key or key == "deadline_ms")]
        columns[name] = write_csv(destination / f"{name}.csv", rows, [*fields, *timestamps])
    manifest = {"version": VERSION, "status": "complete", "database": str(database.resolve()),
        "study_only": study_only, "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        **info, "catalog_version": versions.get("catalog_version"),
        "exported_counts": {name: len(rows) for name, rows in data.items()}}
    write_json(destination / "data_dictionary.json", {"version": VERSION,
        "null": "\\N", "text_escaping": "A leading backslash in source text is prefixed with one additional backslash.",
        "encoding": "UTF-8 with BOM; standard CSV quoting preserves multiline text",
        "booleans": "0/1", "joins": "session_id; (session_id, task_id); checkpoint; oracle_results.routing_id -> routing_decisions.id",
        "notes": ["Development/practice are included unless --study-only is selected.",
            "Only reached checkpoint decisions and actually answered workload items have rows.",
            "Missing optional tables produce header-only CSVs and manifest warnings.",
            "Catalog labels/prices describe the available catalog snapshot; saved task costs/scores are never recomputed.",
            "Decision intervals are descriptive timestamp differences, not a finalized research latency/reliance definition.",
            "CSV text is raw data, not spreadsheet formulas; import text columns as text."],
        "datasets": {name: {key: field_description(key) for key in fields} for name, fields in columns.items()}})
    write_json(destination / "manifest.json", manifest)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=BACKEND_DIR / "data/exports")
    parser.add_argument("--study-only", action="store_true", help="exclude development sessions and practice")
    args = parser.parse_args(argv)
    try:
        destination = export_database(args.database, args.output, args.study_only)
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError):
        print("Export failed: check database path, source schema/JSON, and output permissions. No source writes were performed.")
        return 1
    print(f"CSV export: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
