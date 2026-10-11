"""Study records summary (#41): `python -m app.records` prints what the database holds.

Counts only — no statistical analysis. Development sessions are listed separately and
excluded from study totals. Twelve participants are twelve units, not 96 samples.
"""

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from . import db
from .config import get_settings


def summarize(path: Path) -> dict:
    connection = db.connect(path)
    try:
        sessions = [dict(row) | {"state": json.loads(row["state"])}
                    for row in connection.execute("SELECT * FROM sessions ORDER BY created_at, id")]
        slots = [dict(row) for row in connection.execute("SELECT * FROM allocation_slots ORDER BY slot")]
        routing = [dict(row) for row in connection.execute("SELECT * FROM routing_decisions WHERE applied = 1")]
        usage = {row["purpose"]: dict(row) for row in connection.execute(
            "SELECT purpose, COUNT(*) AS calls, SUM(ok) AS ok, SUM(shown) AS shown,"
            " COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,"
            " COALESCE(SUM(completion_tokens), 0) AS completion_tokens FROM model_calls GROUP BY purpose")}
        oracle = [dict(row) for row in connection.execute("SELECT * FROM oracle_results")]
    finally:
        connection.close()

    study = [s for s in sessions if not s["development"]]
    participants = []
    for session in study:
        state = session["state"]
        tasks = []
        for task_id in ("task-1", "task-2"):
            task = state["tasks"].get(task_id)
            if not task:
                continue
            decisions = task["decisions"].values()
            tasks.append({
                "task": task_id, "scenario": task["scenarioId"], "condition": task["condition"],
                "status": task["status"],
                "elapsedSeconds": round((task["endedAt"] - task["startedAt"]) / 1000) if task["endedAt"] else None,
                "constraintsMet": sum(task["constraints"].values()), "allFourMet": all(task["constraints"].values()),
                "checkpointsReached": len(task["decisions"]),
                "overrideChanges": sum(1 for d in decisions if d["initialModel"] and d["finalModel"]
                                       and d["initialModel"] != d["finalModel"]),
                "workloadScore": task["survey"]["rawScore"], "messages": len(task["messages"]),
            })
        participants.append({"participant": session["participant_id"], "sequence": session["sequence_id"],
                             "step": state["step"], "tasks": tasks})

    study_ids = {s["id"] for s in study}
    final_by_checkpoint = {}
    for session in study:
        for task_id, task in session["state"]["tasks"].items():
            for checkpoint, decision in task["decisions"].items():
                final_by_checkpoint[(session["id"], task_id, checkpoint)] = decision
    routed = [r for r in routing if r["session_id"] in study_ids]
    oracle_study = [o for o in oracle if o["session_id"] in study_ids]
    agreement = Counter()
    for result in oracle_study:
        decision = final_by_checkpoint.get((result["session_id"], result["task_id"], result["checkpoint"]))
        if decision and decision["finalModel"] and result["label"] != "neither":
            agreement["final matches oracle" if decision["finalModel"] == result["label"]
                      else "final differs from oracle"] += 1
    return {
        "allocation": {"used": Counter(s["sequence_id"] for s in slots if s["session_id"]),
                       "free": sum(1 for s in slots if not s["session_id"])},
        "sessions": {"study": len(study), "development": len(sessions) - len(study),
                     "byStep": Counter(s["state"]["step"] for s in study)},
        "participants": participants,
        "routing": Counter(f"{r['condition']} → {r['recommended']}" for r in routed),
        "modelUsage": usage,
        "oracle": {"labels": Counter(o["label"] for o in oracle_study), "agreement": agreement,
                   "pending": sum(1 for r in routed if r["id"] not in {o["routing_id"] for o in oracle_study})},
    }


def format_report(summary: dict) -> str:
    lines = ["Allocation: used per sequence " + json.dumps(dict(sorted(summary["allocation"]["used"].items())))
             + f", free slots {summary['allocation']['free']}",
             f"Sessions: {summary['sessions']['study']} study, {summary['sessions']['development']} development; "
             f"study steps {json.dumps(dict(summary['sessions']['byStep']))}", "Participants:"]
    for participant in summary["participants"]:
        lines.append(f"  {participant['participant']} seq {participant['sequence']} at {participant['step']}")
        for task in participant["tasks"]:
            lines.append(
                f"    {task['task']} {task['scenario']}/{task['condition']}: {task['status']}, "
                f"{task['elapsedSeconds']}s, {task['constraintsMet']}/4 constraints, "
                f"{task['checkpointsReached']} checkpoints, {task['overrideChanges']} override changes, "
                f"{task['messages']} messages, workload {task['workloadScore']}")
    lines.append("Routing (applied): " + json.dumps(dict(summary["routing"])))
    for purpose, usage in summary["modelUsage"].items():
        lines.append(f"Model calls ({purpose}): {usage['calls']} calls, {usage['ok']} ok, {usage['shown']} shown, "
                     f"{usage['prompt_tokens']}+{usage['completion_tokens']} tokens")
    oracle = summary["oracle"]
    lines.append(f"Oracle: labels {json.dumps(dict(oracle['labels']))}, {json.dumps(dict(oracle['agreement']))}, "
                 f"{oracle['pending']} checkpoints pending")
    return "\n".join(lines)


def main() -> int:
    path = Path(get_settings().resolved_database_path)
    if not path.exists():
        print(f"No database at {path}.")
        return 1
    db.init_db(path)  # applies any schema additions without changing study data
    print(format_report(summarize(path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
