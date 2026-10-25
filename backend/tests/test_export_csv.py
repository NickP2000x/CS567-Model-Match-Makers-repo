import csv
import hashlib
import json
import os
import sqlite3
import subprocess
import sys

import pytest

from app import db
from app.export_csv import BASE_COLUMNS, export_database, flatten_snapshot
from app.offline import read_snapshot


def read_csv(directory, name):
    with (directory / f"{name}.csv").open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


@pytest.fixture
def recorded_database(tmp_path):
    path = tmp_path / "recorded.sqlite3"
    db.init_db(path)
    metadata = {"version": "earlier-survey", "min": 0, "max": 100, "increment": 5,
                "items": {"performance": {"orientation": "lower-is-more-workload", "labels": ["A", "B"]}}}
    task = {"scenarioId": "A", "condition": "override", "status": "submitted", "excludedFromResults": False,
            "startedAt": 1000, "deadline": 901000, "endedAt": 5000, "checkpoint": "Venue",
            "plan": {"venue": "A-venue-good", "catering": None, "supplies": []}, "totalCostCents": 30000,
            "constraints": {"budget": True, "capacity": True, "dietary": False, "accessibility": True},
            "survey": {"answers": {"performance": 75}, "metadata": metadata, "rawScore": 37.5, "submittedAt": 6000},
            "messages": [{"id": "m1", "role": "user", "text": '\\N', "checkpoint": "Venue", "createdAt": 2000},
                         {"id": "m2", "role": "assistant", "text": '', "checkpoint": "Venue", "model": "small", "createdAt": 3000}],
            "decisions": {"Venue": {"phase": "committed", "initialModel": "large", "recommendedModel": "small",
                "finalModel": "small", "shownAt": 1000, "initialLockedAt": 1500,
                "recommendationShownAt": 1700, "finalCommittedAt": 1900}},
            "inspectedItems": ["A-venue-good"], "reopens": [{"endedAt": 4000, "reopenedAt": 4500}]}
    state = {"step": "completion", "consent": True, "demographics": {"age": 24, "gender": "Invented — Ω", "priorLlmUsage": "weekly"},
             "feedback": {"interfaceComments": 'Line 1, "quoted"\n第二行', "studyComments": "", "submittedAt": 7000},
             "preparations": {"before-start": {"version": "prep-old", "statements": [{"id": "a", "text": "Original"}],
                 "acknowledgedIds": ["a"], "confirmedAt": 900}},
             "tasks": {"task-1": task, "practice": dict(task, condition="practice", excludedFromResults=True)}}
    with sqlite3.connect(path) as c:
        for sid, development in (("study", 0), ("dev", 1)):
            c.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?)", (sid, sid, 1, development, json.dumps(state), 800, 7000))
        c.execute("INSERT INTO model_calls (session_id,task_id,checkpoint,size,provider,model,step,ok,latency_ms,tools,shown,created_at,purpose)"
                  " VALUES ('study','task-1','Venue','small','mock','fake',1,1,25,'[]',0,3000,'oracle')")
        c.execute("INSERT INTO model_calls (session_id,task_id,checkpoint,size,provider,model,step,ok,latency_ms,tools,shown,created_at,purpose)"
                  " VALUES ('dev','practice','Venue','small','mock','fake',1,1,25,'[]',1,3000,'participant')")
    return path


def test_export_preserves_raw_values_linkage_and_database_bytes(recorded_database, tmp_path):
    before = hashlib.sha256(recorded_database.read_bytes()).hexdigest()
    output = export_database(recorded_database, tmp_path / "exports")
    assert hashlib.sha256(recorded_database.read_bytes()).hexdigest() == before
    sessions = read_csv(output, "sessions")
    assert len(sessions) == 2
    assert sessions[0]["gender"] == "Invented — Ω"
    assert sessions[0]["feedback_interface_comments"] == 'Line 1, "quoted"\n第二行'
    assert sessions[0]["feedback_study_comments"] == ""
    tasks = read_csv(output, "tasks")
    assert len(tasks) == 4
    assert tasks[0]["elapsed_seconds"] == "4.0"
    assert tasks[0]["survey_raw_score"] == "37.5"  # Do not rescore/reverse the raw performance 75.
    assert tasks[0]["survey_performance"] == "75"
    assert tasks[0]["survey_mentalDemand"] == '\\N'
    assert json.loads(tasks[0]["survey_metadata_json"])["items"]["performance"]["orientation"] == "lower-is-more-workload"
    assert read_csv(output, "plan_items")[0]["item_name"] == "Willow Conference Hall"
    assert read_csv(output, "messages")[0]["text"] == '\\\\N'  # Literal source \N escaped, not confused with NULL.
    assert read_csv(output, "messages")[1]["text"] == ""
    choices = read_csv(output, "checkpoint_choices")
    assert len(choices) == 4 and {row["checkpoint"] for row in choices} == {"Venue"}
    assert choices[0]["decision_total_ms"] == "900.0"
    assert choices[0]["initial_choice_ms"] == "500.0"
    assert choices[0]["post_recommendation_ms"] == "200.0"
    assert len(read_csv(output, "task_reopens")) == 4
    assert len(read_csv(output, "inspections")) == 4
    assert read_csv(output, "model_calls")[0]["purpose"] == "oracle"
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["status"] == "complete" and manifest["source_counts"]["sessions"] == 2
    assert manifest["exported_counts"]["messages"] == 8
    assert set(row["session_id"] for row in choices) <= {row["session_id"] for row in sessions}


def test_study_filter_is_explicit_and_preserves_oracle_usage_separation(recorded_database, tmp_path):
    output = export_database(recorded_database, tmp_path / "exports", study_only=True)
    assert [row["session_id"] for row in read_csv(output, "sessions")] == ["study"]
    assert [row["task_id"] for row in read_csv(output, "tasks")] == ["task-1"]
    calls = read_csv(output, "model_calls")
    assert len(calls) == 1 and calls[0]["purpose"] == "oracle"
    assert {row["practice"] for row in read_csv(output, "messages")} == {"0"}


def test_earlier_optional_schema_and_unfinished_tasks_are_not_fabricated(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE sessions (id TEXT, state TEXT)")
        c.execute("INSERT INTO sessions VALUES (?,?)", ("old", json.dumps({"preparations": {"before-start": None},
            "tasks": {"task-1": {"status": "active", "decisions": {"Venue": None}}, "task-2": None}})))
        c.execute("CREATE TABLE model_calls (id INTEGER, session_id TEXT, task_id TEXT, model TEXT)")
        c.execute("INSERT INTO model_calls VALUES (1,'old','task-1','earlier')")
        c.execute("INSERT INTO model_calls VALUES (2,'orphan','task-1','earlier')")
    output = export_database(path, tmp_path / "exports")
    assert len(read_csv(output, "model_calls")) == 2
    assert read_csv(output, "model_calls")[0]["purpose"] == '\\N'
    assert read_csv(output, "tasks")[0]["elapsed_seconds"] == '\\N'
    assert read_csv(output, "tasks")[0]["all_four_met"] == '\\N'
    assert len(read_csv(output, "tasks")) == 1
    assert read_csv(output, "preparations") == []
    assert read_csv(output, "checkpoint_choices") == []
    assert read_csv(output, "survey_responses") == []
    warnings = json.loads((output / "manifest.json").read_text())["warnings"]
    assert any("purpose is absent" in warning for warning in warnings)
    assert any("without a matching session" in warning for warning in warnings)
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 2


def test_empty_exports_have_headers_and_fresh_directories(tmp_path):
    path = tmp_path / "empty.sqlite3"
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE sessions (id TEXT, state TEXT)")
    first = export_database(path, tmp_path / "exports")
    second = export_database(path, tmp_path / "exports")
    assert first != second
    for table in BASE_COLUMNS:
        assert (first / f"{table}.csv").read_text(encoding="utf-8-sig").splitlines()[0]
        assert read_csv(first, table) == []
    header = (first / "tasks.csv").read_text(encoding="utf-8-sig").splitlines()[0]
    assert "survey_raw_score" in header and "started_at_utc" in header


def test_invalid_nonobject_state_does_not_silently_export_an_empty_session(tmp_path):
    path = tmp_path / "invalid.sqlite3"
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE sessions (id TEXT, state TEXT)")
        c.execute("INSERT INTO sessions VALUES ('bad','[]')")
    with pytest.raises(ValueError, match="JSON object"):
        export_database(path, tmp_path / "exports")
    assert not (tmp_path / "exports").exists()


def test_cli_does_not_load_provider_configuration_or_create_missing_database(recorded_database, tmp_path):
    env = dict(os.environ, MODEL_MODE="invalid", ROUTER_MODE="invalid")
    result = subprocess.run([sys.executable, "-m", "app.export_csv", "--database", str(recorded_database),
                             "--output", str(tmp_path / "cli")], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    missing = tmp_path / "does-not-exist.sqlite3"
    result = subprocess.run([sys.executable, "-m", "app.export_csv", "--database", str(missing),
                             "--output", str(tmp_path / "cli")], env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert not missing.exists()


def test_snapshot_does_not_mix_sessions_from_a_concurrent_commit(recorded_database):
    with sqlite3.connect(recorded_database) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
    with read_snapshot(recorded_database) as reader:
        assert reader.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 2
        with sqlite3.connect(recorded_database) as writer:
            writer.execute("INSERT INTO sessions VALUES ('later','later',1,1,'{}',800,7000)")
        datasets, info = flatten_snapshot(reader)
        assert len(datasets["sessions"]) == 2
        assert info["source_counts"]["sessions"] == 2
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            reader.execute("DELETE FROM sessions")
