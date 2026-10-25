import argparse
import hashlib
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app import calibrate
from app.config import Settings
from app.definitions import FIXTURES
from app.models import ModelError
from tests.fakes import ScriptedClient, answer, tool


@pytest.fixture
def corpus():
    payload = json.loads((FIXTURES / "catalog.json").read_text())
    connection = calibrate.catalog_snapshot(payload)
    data, references = calibrate.default_cases(connection, payload)
    yield payload, connection, data, references
    connection.close()


def clients_for(plan, small_error=None):
    return {"small": ScriptedClient("small", [small_error or tool("submit_plan", plan)]),
            "large": ScriptedClient("large", [tool("submit_plan", plan)])}


def result(score, small, large, split="pilot", case_id="case"):
    call = {"ok": True, "latency_ms": 10, "prompt_tokens": 10, "completion_tokens": 5}
    return {"case_id": case_id, "score": score, "split": split, "ok": True, "router_latency_ms": 2,
            "label": calibrate.label(small, large),
            **{size: {"ok": True, "passed": passed, "calls": [call], "prompt_tokens": 10,
                      "completion_tokens": 5, "latency_ms": 10} for size, passed in (("small", small), ("large", large))}}


def test_router_metadata_captures_exposed_checkpoint_identity_only():
    class Scorer:
        model = SimpleNamespace(config=SimpleNamespace(_name_or_path="routellm/test", _commit_hash="revision",
                                                       unrelated_secret="not for export"))

        def score(self, text):
            return .5
    assert calibrate.scorer_metadata(Scorer().score) == {"router_checkpoint": "routellm/test",
                                                       "router_checkpoint_revision": "revision"}


def test_default_corpus_covers_scenarios_stages_and_valid_frozen_plans(corpus):
    payload, connection, data, _ = corpus
    calibrate.validate_cases(data, payload, connection)
    assert len(data["cases"]) == 24
    assert {(c["scenario_id"], c["checkpoint"]) for c in data["cases"]} == {
        (sid, cp) for sid in ("A", "B") for cp in calibrate.CHECKPOINTS}
    assert calibrate.digest(data) == calibrate.digest(calibrate.default_cases(connection, payload)[0])
    assert connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 2
    with pytest.raises(Exception, match="readonly"):
        connection.execute("DELETE FROM catalog_items")


def test_pair_receives_identical_model_context_and_keeps_actual_proposals(corpus):
    payload, connection, data, references = corpus
    case = data["cases"][0]
    clients = clients_for(references["A"])
    row = calibrate.evaluate_case(case, 0, 0, connection, {s["id"]: s for s in payload["scenarios"]},
                                  references, clients, lambda text: 0.5)
    assert row["ok"] and row["label"] == "small"
    assert clients["small"].requests == clients["large"].requests
    assert case["question"] in clients["small"].requests[0][0][1]["content"]
    assert row["small"]["plan"] == references["A"] and row["purpose"] == "calibration"
    assert row["small"]["prompt_tokens"] == 20
    assert row["evaluation_order"] == ("small", "large")
    again = calibrate.evaluate_case(case, 0, 1, connection, {s["id"]: s for s in payload["scenarios"]},
                                    references, clients_for(references["A"]), lambda text: 0.5)
    assert again["evaluation_order"] == ("large", "small")


def test_provider_failures_still_evaluate_the_other_model_and_do_not_leak_messages(corpus):
    payload, connection, data, references = corpus
    clients = clients_for(references["A"], ModelError("sensitive-provider-message"))
    row = calibrate.evaluate_case(data["cases"][0], 0, 0, connection, {s["id"]: s for s in payload["scenarios"]},
                                  references, clients, lambda text: 0.2)
    assert not row["ok"] and row["small"]["passed"] is None
    assert row["large"]["ok"] and row["label"] is None
    assert len(clients["large"].requests) == 1
    assert "sensitive-provider-message" not in json.dumps(row)
    report = calibrate.calibration_report([row], [0, .5, 1], 0)
    assert report["recommendation"] is None and not report["complete"]
    assert report["actual_evaluation_usage"]["small"]["failed_calls"] == 1


def test_no_submitted_plan_is_a_quality_failure_not_a_transport_error(corpus):
    payload, connection, data, references = corpus
    clients = clients_for(references["A"])
    clients["small"] = ScriptedClient("small", [answer("Here is advice without a submitted plan.")])
    row = calibrate.evaluate_case(data["cases"][0], 0, 0, connection,
        {s["id"]: s for s in payload["scenarios"]}, references, clients, lambda text: .8)
    assert row["ok"] and row["label"] == "large"
    assert row["small"]["plan"] is None and row["small"]["passed"] is False
    assert row["small"]["transcript"][-1]["content"] == "Here is advice without a submitted plan."


@pytest.mark.parametrize("score", [float("nan"), -0.1, 1.1, None])
def test_invalid_router_scores_do_not_fall_back(corpus, score):
    payload, connection, data, references = corpus
    row = calibrate.evaluate_case(data["cases"][0], 0, 0, connection, {s["id"]: s for s in payload["scenarios"]},
        references, clients_for(references["A"]), lambda text: score)
    assert not row["ok"] and row["score"] is None and row["router_error"]


def test_threshold_equality_extremes_neither_and_missing_usage():
    row = result(.5, True, False)
    assert calibrate.threshold_metrics([row], .5)["selected_pass_rate"] == 0
    assert calibrate.threshold_metrics([row], .500001)["selected_pass_rate"] == 1
    assert calibrate.threshold_metrics([result(1, False, True)], 1)["large_fraction"] == 1
    rows = [result(.2, True, True, case_id="both"), result(.8, False, True, case_id="large"),
            result(.3, True, False, case_id="small"), result(.6, False, False, case_id="neither")]
    metrics = calibrate.threshold_metrics(rows, .4)
    assert metrics["selected_pass_rate"] == .75
    assert metrics["oracle_agreement"] == 1 and metrics["oracle_agreement_denominator"] == 3
    assert metrics["neither_passes"] == 1
    assert metrics["selected_tokens"] == 60
    rows[0]["small"]["prompt_tokens"] = None
    assert calibrate.threshold_metrics(rows, .4)["selected_tokens"] is None


def test_holdout_is_not_used_to_select_threshold_and_errors_prevent_recommendation():
    rows = [result(.4, True, True), result(.8, False, True, split="holdout", case_id="held")]
    report = calibrate.calibration_report(rows, [0, .5, 1], 1)
    assert report["recommendation"]["threshold"] == .5
    assert report["holdout"]["selected_pass_rate"] == 1
    assert report["recommendation"]["evaluated_contexts"] == 1
    rows[1]["ok"] = False
    assert calibrate.calibration_report(rows, [0, .5, 1], 1)["recommendation"] is None


def test_adaptive_grid_resolves_narrow_pilot_bands_without_holdout_leakage():
    rows = [result(.481, True, True), result(.489, False, True), result(.123, True, True, split="holdout")]
    assert calibrate.candidate_thresholds(rows) == [0, .485, 1]


@pytest.mark.parametrize("value", ["nan", "inf", "-0.01", "1.01", "", "0.5,nope"])
def test_threshold_cli_input_rejects_nonfinite_or_invalid_values(value):
    with pytest.raises(argparse.ArgumentTypeError):
        calibrate.threshold_list(value)


def test_dry_run_is_explicit_deterministic_and_does_not_load_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(calibrate, "Settings", lambda **kw: pytest.fail("dry-run loaded settings"))
    with pytest.raises(SystemExit) as raised:
        calibrate.main([])
    assert raised.value.code == 2
    assert calibrate.main(["--dry-run", "--output", str(tmp_path), "--min-pass-rate", ".7"]) == 0
    output = next(tmp_path.glob("calibration-*"))
    manifest = json.loads((output / "manifest.json").read_text())
    rows = [json.loads(line) for line in (output / "evaluations.jsonl").read_text().splitlines()]
    assert manifest["status"] == "complete" and manifest["configuration"]["mode"] == "dry-run"
    assert len(rows) == 24 and all(r["simulated"] for r in rows)
    report = json.loads((output / "report.json").read_text())
    assert report["recommendation"]["selected_pass_rate"] >= .7
    assert report["actual_evaluation_usage"]["small"]["actual_calls"] == 0


def test_real_cli_uses_injected_pair_without_touching_the_configured_database(tmp_path, monkeypatch, capsys):
    database = tmp_path / "participant.sqlite3"
    database.write_bytes(b"existing participant data")
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    settings = Settings(_env_file=None, model_mode="real", router_mode="mock", routellm_router="bert",
        small_model="ollama:small", large_model="ollama:large", database_path=database,
        openai_api_key="synthetic-key-not-for-output",
        openai_base_url="https://user:synthetic-endpoint-secret@example.test/v1?token=synthetic-query-secret")
    reference = {"venue": "A-venue-good", "catering": "A-food-good", "supplies": ["A-supplies-good"]}
    monkeypatch.setattr(calibrate, "Settings", lambda **kw: settings)
    monkeypatch.setattr(calibrate, "build_clients", lambda s: clients_for(reference))
    monkeypatch.setattr(calibrate, "load_routellm_scorer", lambda *args: lambda text: .5)
    output = tmp_path / "results"
    assert calibrate.main(["--real", "--output", str(output), "--limit", "1"]) == 0
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    run = next(output.iterdir())
    artifact_text = "\n".join(p.read_text(encoding="utf-8-sig") for p in run.iterdir())
    assert "synthetic-key-not-for-output" not in artifact_text + capsys.readouterr().out
    assert "synthetic-endpoint-secret" not in artifact_text and "synthetic-query-secret" not in artifact_text
    assert json.loads((run / "manifest.json").read_text())["configuration"]["mode"] == "real"


def test_invalid_contexts_fail_before_real_calls_and_cli_dry_run_ignores_invalid_settings(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"version": "bad", "synthetic": True, "cases": [{"id": "x", "scenario_id": "practice"}]}))
    monkeypatch.setattr(calibrate, "Settings", lambda **kw: pytest.fail("invalid corpus loaded real settings"))
    assert calibrate.main(["--real", "--cases", str(bad), "--output", str(tmp_path / "invalid")]) == 1
    assert not (tmp_path / "invalid").exists()
    env = dict(os.environ, MODEL_MODE="invalid", ROUTER_MODE="invalid")
    result = subprocess.run([sys.executable, "-m", "app.calibrate", "--dry-run", "--limit", "1",
        "--output", str(tmp_path / "subprocess")], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_real_calls_need_real_model_mode_and_failures_get_artifacts(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, model_mode="mock", router_mode="mock")
    monkeypatch.setattr(calibrate, "Settings", lambda **kw: settings)
    monkeypatch.setattr(calibrate, "build_clients", lambda s: pytest.fail("mock configuration made real calls"))
    assert calibrate.main(["--real", "--output", str(tmp_path / "blocked")]) == 1
    assert not (tmp_path / "blocked").exists()
    settings = Settings(_env_file=None, model_mode="real", router_mode="mock", routellm_router="bert",
                        small_model="ollama:small", large_model="ollama:large")
    plan = {"venue": "A-venue-good", "catering": None, "supplies": []}
    monkeypatch.setattr(calibrate, "build_clients", lambda s: clients_for(plan, ModelError("not for export")))
    monkeypatch.setattr(calibrate, "load_routellm_scorer", lambda *args: lambda text: .5)
    assert calibrate.main(["--real", "--limit", "1", "--output", str(tmp_path / "failed")]) == 1
    run = next((tmp_path / "failed").iterdir())
    assert json.loads((run / "manifest.json").read_text())["status"] == "completed_with_errors"
    assert json.loads((run / "report.json").read_text())["recommendation"] is None
