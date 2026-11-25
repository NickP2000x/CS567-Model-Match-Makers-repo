"""Synthetic checks: no real participant data, app imports, settings or providers."""

import contextlib
import copy
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "analyze_csv.py"
spec = importlib.util.spec_from_file_location("analyze_csv", SCRIPT)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def task(sid, tid, condition, seconds, passed=6, score=50, version="adapted-v2"):
    checks = {key: i < passed for i, key in enumerate(analysis.CONSTRAINTS)}
    # A five-point scale: correctly oriented score 50 corresponds to response 3.
    metadata = {"version": version, "min": 1, "max": 5, "increment": 1,
                "items": {key: {"orientation": "higher-is-more-workload"} for key in analysis.DIMENSIONS}}
    response = 1 + score / 25
    return {"session_id": sid, "task_id": tid, "condition": condition, "status": "submitted",
            "practice": "0", "excluded_from_results": "0", "started_at_ms": "1000",
            "ended_at_ms": str(1000 + seconds * 1000), "elapsed_seconds": str(seconds),
            "deadline_ms": "901000", "constraints_json": json.dumps(checks),
            "constraints_satisfied": str(passed), "all_met": "1" if passed == 6 else "0",
            "survey_raw_score": str(score), "survey_version": version,
            "survey_submitted_at_ms": str(2000 + seconds * 1000),
            "survey_metadata_json": json.dumps(metadata),
            "survey_answers_json": json.dumps(dict.fromkeys(analysis.DIMENSIONS, response))}


def snapshot():
    data = {name: [] for name in analysis.SOURCES}
    data["sessions"] = [
        {"session_id": sid, "participant_id": f"synthetic-{sid}", "prolific_id": f"PRIVATE{sid}",
         "development": "0", "consent": "1", "sequence_id": str(i + 1), "step": "completion",
         "simulated": "0", "router_simulated": "0"}
        for i, sid in enumerate(("s1", "s2"))]
    data["tasks"] = [task("s1", "task-1", "automatic", 100, 4, 25),
                     task("s1", "task-2", "override", 120, 6, 50),
                     task("s2", "task-1", "override", 240, 5, 75),
                     task("s2", "task-2", "automatic", 200, 6, 50)]
    return data


def find(rows, metric, condition=None):
    return next(row for row in rows if row["metric"] == metric and (condition is None or row["condition"] == condition))


def write_snapshot(directory, data):
    for name, rows in data.items():
        if rows is None:
            continue
        fields = sorted(set(analysis.REQUIRED[name]) | {key for row in rows for key in row})
        with (directory / (name + ".csv")).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows({key: row.get(key) if row.get(key) is not None else "\\N" for key in fields} for row in rows)


class AnalysisTests(unittest.TestCase):
    def run_analysis(self, data=None, include=False):
        return analysis.analyze(data or snapshot(), {}, include)

    def test_known_paired_differences_quartiles_and_binary_counts(self):
        summary, pairs, _, report = self.run_analysis()
        auto = find(summary, "elapsed_seconds", "automatic")
        self.assertEqual((auto["n"], auto["median"], auto["q1"], auto["q3"]), (2, 150, 125, 175))
        difference = find(pairs, "elapsed_seconds")
        self.assertEqual((difference["n"], difference["median"], difference["q1"], difference["q3"]), (2, 30, 25, 35))
        quality = find(summary, "all_met:" + "+".join(analysis.CONSTRAINTS), "automatic")
        self.assertEqual((quality["events"], quality["event_rate"]), (1, .5))
        self.assertEqual(find(pairs, "workload:adapted-v2")["median"], 25)
        self.assertEqual(report["counts"]["sessions_with_both_ended_conditions"], 2)

    def test_filters_partial_tasks_and_timeouts_without_fabrication(self):
        data = snapshot()
        data["sessions"] += [{"session_id": "dev", "participant_id": "dev", "development": "1", "consent": "1"}]
        data["tasks"] += [task("dev", "task-1", "automatic", 999), task("s1", "practice", "practice", 1)]
        data["tasks"][1].update(status="active", ended_at_ms=None, survey_raw_score=None)
        data["tasks"][2].update(status="timed-out", ended_at_ms="901000", elapsed_seconds="900")
        summary, pairs, _, report = self.run_analysis(data)
        self.assertEqual(report["counts"]["sessions_with_both_ended_conditions"], 1)
        self.assertEqual(report["exclusions"]["development_sessions"], 1)
        self.assertEqual(report["exclusions"]["practice_tasks"], 1)
        self.assertEqual(report["exclusions"]["unfinished_experimental_tasks"], 1)
        self.assertEqual(find(pairs, "elapsed_seconds")["median"], 700)
        self.assertEqual(find(summary, "timed_out", "override")["events"], 1)
        self.assertEqual(find(summary, "submitted_elapsed_seconds", "override")["n"], 0)
        self.assertEqual(find(summary, "elapsed_seconds", "automatic")["n"], 2)

    def test_legacy_constraints_and_survey_versions_not_pooled(self):
        data = snapshot()
        legacy = data["tasks"][1]
        legacy["constraints_json"] = json.dumps(dict.fromkeys(analysis.CONSTRAINTS[:4], True))
        legacy.update(constraints_satisfied="4", all_met="1", survey_version="other-v1")
        metadata = json.loads(legacy["survey_metadata_json"])
        metadata["version"] = "other-v1"
        legacy["survey_metadata_json"] = json.dumps(metadata)
        summary, pairs, _, report = self.run_analysis(data)
        self.assertEqual(find(pairs, "constraints_satisfied:" + "+".join(analysis.CONSTRAINTS))["n"], 1)
        self.assertEqual(find(pairs, "workload:other-v1")["n"], 0)
        self.assertEqual(len(report["constraint_definitions"]), 2)
        self.assertIn("mixed_survey_versions_reported_separately", report["warnings"])

    def test_workload_orientation_invalid_score_and_nonfinite_values(self):
        data = snapshot()
        row = data["tasks"][0]
        metadata, answers = json.loads(row["survey_metadata_json"]), json.loads(row["survey_answers_json"])
        metadata["items"]["performance"]["orientation"] = "lower-is-more-workload"
        answers["performance"] = 4  # Reversed 4/5 is the same workload as forward 2/5.
        row.update(survey_metadata_json=json.dumps(metadata), survey_answers_json=json.dumps(answers))
        data["tasks"][1]["survey_raw_score"] = "99"
        data["tasks"][2]["survey_raw_score"] = "NaN"
        summary, pairs, _, report = self.run_analysis(data)
        self.assertEqual(find(summary, "workload:adapted-v2", "automatic")["n"], 2)
        self.assertEqual(find(summary, "workload:adapted-v2", "override")["n"], 0)
        self.assertEqual(find(pairs, "workload:adapted-v2")["n"], 0)
        self.assertEqual(report["warnings"]["workload_score_or_metadata_mismatch"], 1)

    def test_calls_exclude_oracle_keep_failures_and_unknown_usage_missing(self):
        data = snapshot()
        base = {"session_id": "s1", "task_id": "task-1", "purpose": "participant", "size": "large",
                "model": "synthetic-large", "shown": "0", "ok": "1", "prompt_tokens": "10", "completion_tokens": "2"}
        data["model_calls"] = [dict(base, id="1"), dict(base, id="2", ok="0", prompt_tokens=None),
                               dict(base, id="3", purpose="oracle", prompt_tokens="9000")]
        summary, _, _, report = self.run_analysis(data)
        self.assertEqual(find(summary, "participant_model_calls", "automatic")["mean"], 1)
        self.assertEqual(find(summary, "participant_prompt_tokens", "automatic")["n"], 1)  # Only s2 has known zero usage.
        self.assertEqual(find(summary, "participant_completion_tokens", "automatic")["mean"], 2)
        self.assertEqual(report["call_accounting_for_included_ended_tasks"]["oracle_calls"], 1)
        self.assertEqual(report["call_accounting_for_included_ended_tasks"]["participant_failed_calls"], 1)
        data["model_calls"] = None
        summary, _, _, _ = self.run_analysis(data)
        self.assertFalse(any(row["metric"] == "participant_model_calls" for row in summary))

    def test_override_change_is_not_recommendation_override_and_oracle_join(self):
        data = snapshot()
        base = {"session_id": "s1", "task_id": "task-2", "phase": "committed", "final_model": "large",
                "initial_model": "small", "recommended_model": "large", "initial_choice_ms": "1500",
                "post_recommendation_ms": "2500", "decision_total_ms": "4000"}
        data["checkpoint_choices"] = [dict(base, checkpoint="Venue"), dict(base, checkpoint="Catering")]
        data["routing_decisions"] = [dict(base, id="10", checkpoint="Venue", ok="1", applied="1"),
                                     dict(base, id="11", checkpoint="Catering", ok="1", applied="1")]
        data["oracle_results"] = [dict(base, routing_id="10", checkpoint="Venue", label="large", small_passed="0", large_passed="1"),
                                  dict(base, routing_id="11", checkpoint="Catering", label="neither", small_passed="0", large_passed="0")]
        summary, _, routing, _ = self.run_analysis(data)
        self.assertEqual(find(summary, "initial_choice_change_rate", "override")["mean"], 1)
        self.assertEqual(find(summary, "override_recommendation_rate", "override")["mean"], 0)
        self.assertEqual(find(summary, "mean_post_recommendation_seconds", "override")["mean"], 2.5)
        self.assertEqual(find(summary, "oracle_preferred_choice_agreement", "override")["mean"], 1)
        over = next(row for row in routing if row["condition"] == "override")
        self.assertEqual(over["final_oracle_agreement_denominator"], 1)
        self.assertEqual(over["oracle_neither_passes"], 1)

    def test_ambiguous_routes_and_inconsistent_oracles_are_not_scored(self):
        data = snapshot()
        base = {"session_id": "s1", "task_id": "task-1", "checkpoint": "Venue", "ok": "1", "applied": "1"}
        data["routing_decisions"] = [dict(base, id="1"), dict(base, id="2")]
        data["oracle_results"] = [dict(base, routing_id="1", label="large", small_passed="1", large_passed="1")]
        _, _, _, report = self.run_analysis(data)
        self.assertEqual(report["warnings"]["ambiguous_applied_routes_at_checkpoint"], 1)
        data["routing_decisions"].pop()
        _, _, _, report = self.run_analysis(data)
        self.assertEqual(report["warnings"]["inconsistent_oracle_labels"], 1)

    def test_conflicting_participants_and_duplicate_conditions_fail(self):
        data = snapshot()
        data["sessions"][1]["prolific_id"] = data["sessions"][0]["prolific_id"]
        with self.assertRaisesRegex(analysis.AnalysisError, "identifier occurs"):
            self.run_analysis(data)
        data = snapshot()
        data["tasks"][1]["condition"] = "automatic"
        with self.assertRaisesRegex(analysis.AnalysisError, "same condition"):
            self.run_analysis(data)

    def test_cli_outputs_readonly_private_by_default_and_no_app_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "private export"
            source.mkdir()
            data = snapshot()
            data["sessions"][0]["feedback_interface_comments"] = 'PRIVATE COMMENT, "quoted"\nsecond line'
            write_snapshot(source, data)
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}
            env = dict(os.environ, MODEL_MODE="invalid", OPENAI_API_KEY="not-a-real-key", DATABASE_PATH="do-not-open.sqlite3")
            result = subprocess.run([sys.executable, "-B", "-I", str(SCRIPT), "--input", str(source), "--output", str(root / "results")],
                                    capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = next((root / "results").iterdir())
            self.assertEqual({p.name for p in output.iterdir()}, {"condition_summary.csv", "paired_comparisons.csv", "routing_summary.csv",
                                                                 "data_quality_report.json", "paper_tables.tex", "results_summary.md"})
            text = "\n".join(p.read_text(encoding="utf-8-sig") for p in output.iterdir())
            for private in ("PRIVATEs1", "PRIVATEs2", "PRIVATE COMMENT", "not-a-real-key"):
                self.assertNotIn(private, text + result.stdout + result.stderr)
            self.assertIn(r"50.0\%", (output / "paper_tables.tex").read_text())
            self.assertIn("No hypothesis tests", text)
            self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()})
            self.assertFalse((root / "do-not-open.sqlite3").exists())

    def test_csv_duplicates_manifest_and_incomplete_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            data = snapshot()
            data["tasks"].append(copy.deepcopy(data["tasks"][0]))
            write_snapshot(source, data)
            loaded, provenance = analysis.load_snapshot(source)
            self.assertEqual(len(loaded["tasks"]), 4)
            self.assertEqual(provenance["identical_duplicates_removed"]["tasks"], 1)
            data["tasks"][-1]["status"] = "active"
            write_snapshot(source, data)
            with self.assertRaisesRegex(analysis.AnalysisError, "Conflicting duplicate"):
                analysis.load_snapshot(source)
            data["tasks"].pop()
            write_snapshot(source, data)
            (source / "manifest.json").write_text(json.dumps({"status": "complete", "exported_counts": {"tasks": 999}}))
            with self.assertRaisesRegex(analysis.AnalysisError, "Manifest row count"):
                analysis.load_snapshot(source)

    def test_no_eligible_records_produces_diagnostics_not_fake_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            source.mkdir()
            data = snapshot()
            for session in data["sessions"]:
                session["development"] = "1"
            write_snapshot(source, data)
            with contextlib.redirect_stdout(io.StringIO()):
                status = analysis.main(["--input", str(source), "--output", str(root / "out")])
            self.assertEqual(status, 2)
            report = json.loads(next((root / "out").glob("*/data_quality_report.json")).read_text())
            self.assertEqual(report["counts"]["included_ended_tasks"], 0)
            _, _, _, included = self.run_analysis(data, include=True)
            self.assertEqual(included["counts"]["included_ended_tasks"], 4)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(analysis.main(["--input", str(source), "--output", str(source / "bad")]), 2)

    def test_latex_escapes_untrusted_version_text(self):
        self.assertEqual(analysis.latex("a_%&{b}"), r"a\_\%\&\{b\}")


if __name__ == "__main__":
    unittest.main()
