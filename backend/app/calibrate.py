"""Offline synthetic paired-plan evaluation; reports thresholds without changing study settings."""

import argparse
import hashlib
import importlib.metadata
import json
import math
import sqlite3
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .agent import CatalogTools
from .config import Settings
from .definitions import CHECKPOINTS, FIXTURES
from .models import build_clients
from .offline import BACKEND_DIR, json_text, new_run_directory, write_csv, write_json
from .oracle import OracleFailed, STAGE_CHECKS, label, oracle_prompt, propose
from .router import OPENAI_ROUTERS, load_routellm_scorer, routing_prompt

VERSION = "paired-routing-calibration-v1"


def scorer_metadata(scorer):
    # Inspect only public checkpoint identity fields, never serialize a router/client.
    model = getattr(getattr(scorer, "__self__", None), "model", None)
    config = getattr(model, "config", None)
    reference = getattr(config, "_name_or_path", None)
    revision = getattr(config, "_commit_hash", None)
    return {"router_checkpoint": reference if isinstance(reference, str) else None,
            "router_checkpoint_revision": revision if isinstance(revision, str) else None}


def digest(value):
    return hashlib.sha256(json_text(value).encode()).hexdigest()


def catalog_snapshot(payload):
    """Only the two catalog tables, in memory; never open the participant database."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript("CREATE TABLE catalog_scenarios(id TEXT PRIMARY KEY,data TEXT);"
                             "CREATE TABLE catalog_items(id TEXT PRIMARY KEY,scenario_id TEXT,category TEXT,position INTEGER,data TEXT);")
    try:
        connection.executemany("INSERT INTO catalog_scenarios VALUES (?,?)",
            [(s["id"], json_text(s)) for s in payload["scenarios"]])
        connection.executemany("INSERT INTO catalog_items VALUES (?,?,?,?,?)",
            [(item["id"], item["scenarioId"], item["category"], i, json_text(item)) for i, item in enumerate(payload["items"])])
        connection.commit()
        connection.execute("PRAGMA query_only=ON")
    except Exception:
        connection.close()
        raise
    return connection


def default_cases(connection, payload):
    cases = []
    references = {}
    empty = {"venue": None, "catering": None, "supplies": []}
    for scenario in (s for s in payload["scenarios"] if s["id"] in ("A", "B")):
        sid = scenario["id"]
        reference = {"venue": f"{sid}-venue-good", "catering": f"{sid}-food-good", "supplies": [f"{sid}-supplies-good"]}
        tools = CatalogTools(connection, sid)
        check = tools.run("check_plan", json_text(reference))
        if not check.get("allConstraintsMet"):
            raise ValueError("Default corpus requires a feasible reference plan in each scenario.")
        references[sid] = reference
        for checkpoint in CHECKPOINTS:
            prefix = dict(empty)
            if checkpoint != "Venue":
                prefix["venue"] = reference["venue"]
            if checkpoint in ("Supplies", "Final constraint check"):
                prefix["catering"] = reference["catering"]
            if checkpoint == "Final constraint check":
                prefix = reference
            repair = dict(reference)
            if checkpoint == "Venue":
                repair["venue"] = f"{sid}-venue-capacity"
            elif checkpoint == "Catering":
                repair["catering"] = f"{sid}-food-diet"
            elif checkpoint == "Supplies":
                repair["supplies"] = [f"{sid}-supplies-cost"]
            else:
                repair["venue"] = f"{sid}-venue-access"
            for variant, plan in (("initial", prefix), ("review", reference), ("repair", repair)):
                cases.append({"id": f"{sid}-{checkpoint}-{variant}", "scenario_id": sid, "checkpoint": checkpoint,
                    "split": "pilot", "plan": plan,
                    "question": f"Compare the catalog options for {checkpoint} and propose a plan that meets the requirements."})
    if len(references) != 2:
        raise ValueError("Calibration needs both A and B scenarios.")
    return {"version": "synthetic-stage-contexts-v1", "synthetic": True, "cases": cases}, references


def validate_cases(corpus, payload, connection):
    if corpus.get("synthetic") is not True or not corpus.get("version") or not corpus.get("cases"):
        raise ValueError("Provide a versioned corpus explicitly marked synthetic=true.")
    scenarios = {s["id"] for s in payload["scenarios"]}
    seen = set()
    for case in corpus["cases"]:
        if not isinstance(case.get("id"), str) or case["id"] in seen:
            raise ValueError("Context IDs must be unique strings.")
        seen.add(case["id"])
        if case.get("scenario_id") not in scenarios & {"A", "B"} or case.get("checkpoint") not in CHECKPOINTS:
            raise ValueError("Contexts must use an experimental scenario and known checkpoint.")
        if case.get("split", "pilot") not in ("pilot", "holdout") or not isinstance(case.get("question"), str):
            raise ValueError("Contexts need a question and a pilot/holdout split.")
        plan = case.get("plan")
        if not isinstance(plan, dict) or set(plan) != {"venue", "catering", "supplies"}:
            raise ValueError("Each context needs a complete plan shape (null choices are allowed).")
        if not isinstance(plan["supplies"], list) or len(set(plan["supplies"])) != len(plan["supplies"]):
            raise ValueError("Supply selections must be a list of distinct item IDs.")
        result = CatalogTools(connection, case["scenario_id"]).run("check_plan", json_text(plan))
        if "error" in result:
            raise ValueError("A context plan contains invalid catalog IDs/categories.")


def proposal_record(proposal=None, failure=None):
    calls = failure.calls if failure else proposal.calls
    records = []
    for call in calls:
        record = asdict(call)
        # Do not copy exception messages from arbitrary injected/provider clients.
        if record["error"]:
            record["error"] = "model_provider_error"
        records.append(record)
    return {"ok": failure is None, "passed": proposal.passed if proposal else None,
            "plan": proposal.plan if proposal else None, "calls": records,
            "transcript": failure.trace if failure else proposal.trace,
            "latency_ms": sum(c.latency_ms for c in calls),
            "prompt_tokens": sum(c.prompt_tokens for c in calls) if calls and all(c.prompt_tokens is not None for c in calls) else None,
            "completion_tokens": sum(c.completion_tokens for c in calls) if calls and all(c.completion_tokens is not None for c in calls) else None}


def evaluate_case(case, index, repeat, connection, scenarios, references, clients=None, scorer=None, max_steps=4):
    scenario = scenarios[case["scenario_id"]]
    row = {"purpose": "calibration", "case_id": case["id"], "repeat": repeat, "split": case.get("split", "pilot"),
           "scenario_id": case["scenario_id"], "checkpoint": case["checkpoint"], "plan": case["plan"],
           "question": case["question"], "simulated": clients is None,
           "router_prompt": routing_prompt(scenario, case["checkpoint"], case["plan"], [{"role": "user", "text": case["question"]}]),
           "model_system_prompt": oracle_prompt(scenario, case["checkpoint"], case["plan"]),
           "model_user_prompt": case["question"] + "\nPropose and submit the plan for this stage.",
           "router_error": None}
    started = time.monotonic()
    try:
        score = [0.2, 0.8, 0.3, 0.6][index % 4] if clients is None else float(scorer(row["router_prompt"]))
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Invalid router score")
        row["score"] = score
    except Exception as error:
        row.update(score=None, router_error=type(error).__name__)
    row["router_latency_ms"] = int((time.monotonic() - started) * 1000) if clients is not None else 0
    order = ("small", "large") if (index + repeat) % 2 == 0 else ("large", "small")
    row["evaluation_order"] = order
    for size in order:
        if clients is None:
            passed = ([True, False, True, False] if size == "small" else [True, True, False, False])[index % 4]
            plan = references[case["scenario_id"]] if passed else {"venue": None, "catering": None, "supplies": []}
            result = CatalogTools(connection, case["scenario_id"]).run("check_plan", json_text(plan))
            row[size] = {"ok": True, "passed": all(result["constraints"][k] for k in STAGE_CHECKS[case["checkpoint"]]),
                         "plan": plan, "calls": [], "latency_ms": 0, "prompt_tokens": None, "completion_tokens": None}
        else:
            try:
                proposal = propose(clients[size], connection, scenario, case["checkpoint"], case["plan"], max_steps,
                                   question=case["question"])
                row[size] = proposal_record(proposal)
            except OracleFailed as failure:
                row[size] = proposal_record(failure=failure)
    row["ok"] = row["score"] is not None and row["small"]["ok"] and row["large"]["ok"]
    row["label"] = label(row["small"]["passed"], row["large"]["passed"]) if row["small"]["ok"] and row["large"]["ok"] else None
    return row


def threshold_metrics(rows, threshold):
    valid = [r for r in rows if r["ok"]]
    selected = [(r, "large" if r["score"] >= threshold else "small") for r in valid]
    labelled = [(r, size) for r, size in selected if r["label"] != "neither"]
    tokens = [r[size][key] for r, size in selected for key in ("prompt_tokens", "completion_tokens")]
    n = len(valid)
    return {"threshold": threshold, "evaluated_contexts": n, "distinct_contexts": len({r["case_id"] for r in valid}),
        "excluded_errors": len(rows) - n, "neither_passes": sum(r["label"] == "neither" for r in valid),
        "large_fraction": sum(size == "large" for _, size in selected) / n if n else None,
        "selected_pass_rate": sum(r[size]["passed"] for r, size in selected) / n if n else None,
        "always_large_pass_rate": sum(r["large"]["passed"] for r in valid) / n if n else None,
        "always_small_pass_rate": sum(r["small"]["passed"] for r in valid) / n if n else None,
        "oracle_available_pass_rate": sum(r["label"] != "neither" for r in valid) / n if n else None,
        "oracle_agreement": sum(r["label"] == size for r, size in labelled) / len(labelled) if labelled else None,
        "oracle_agreement_denominator": len(labelled),
        "selected_model_calls": sum(len(r[size]["calls"]) for r, size in selected),
        "selected_large_model_calls": sum(len(r[size]["calls"]) for r, size in selected if size == "large"),
        "mean_router_latency_ms": sum(r["router_latency_ms"] for r in valid) / n if n else None,
        "selected_tokens": sum(tokens) if tokens and all(t is not None for t in tokens) else None,
        "selected_mean_model_latency_ms": sum(r[size]["latency_ms"] for r, size in selected) / n if n else None}


def calibration_report(rows, thresholds, minimum):
    pilot = [r for r in rows if r["split"] == "pilot"]
    grid = [threshold_metrics(pilot, t) for t in thresholds]
    candidates = [m for m in grid if m["selected_pass_rate"] is not None and m["selected_pass_rate"] >= minimum]
    # Never recommend from a silently reduced sample after provider/router failure.
    best = min(candidates, key=lambda m: (m["large_fraction"], -m["selected_pass_rate"], m["threshold"])) if candidates and all(r["ok"] for r in rows) else None
    usage = {}
    for size in ("small", "large"):
        calls = [call for row in rows for call in row[size]["calls"]]
        usage[size] = {"actual_calls": len(calls), "failed_calls": sum(not c["ok"] for c in calls),
            "latency_ms": sum(c["latency_ms"] for c in calls),
            "known_prompt_tokens": sum(c["prompt_tokens"] for c in calls if c["prompt_tokens"] is not None),
            "known_completion_tokens": sum(c["completion_tokens"] for c in calls if c["completion_tokens"] is not None),
            "calls_missing_usage": sum(c["prompt_tokens"] is None or c["completion_tokens"] is None for c in calls)}
    return {"version": VERSION, "minimum_pilot_pass_rate": minimum, "thresholds": grid,
        "actual_evaluation_usage": usage,
        "recommendation": best,
        "recommendation_rule": "Among error-free pilot candidates meeting the requested pass rate, minimize large fraction; tie-break by higher pass rate then lower threshold. Manual review required.",
        "holdout": threshold_metrics([r for r in rows if r["split"] == "holdout"], best["threshold"]) if best else None,
        "complete": all(r["ok"] for r in rows),
        "limitations": ["Provisional paired-plan oracle, not a measure of participant outcomes or conversational answer quality.",
            "Neither-passes cases count as task failures but are excluded from size-label agreement.",
            "Default corpus is synthetic pilot-only; independent representative holdout/pilot evidence is required.",
            "Repeated contexts are not independent participants. No monetary costs are inferred from token counts.",
            "Missing token usage stays null. Failed samples are reported, never silently scored as model incapability.",
            "The recommended threshold is a report, not an automatic study configuration change."]}


def candidate_thresholds(rows):
    """Resolve narrow score bands without looking at holdout scores/outcomes."""
    scores = sorted({r["score"] for r in rows if r["split"] == "pilot" and r["score"] is not None})
    return sorted({0.0, 1.0, *((a + b) / 2 for a, b in zip(scores, scores[1:]))})


def fraction(value):
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise argparse.ArgumentTypeError("use a finite number between 0 and 1")
    return number


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("use a positive integer")
    return number


def threshold_list(value):
    try:
        return sorted(set(fraction(v.strip()) for v in value.split(",")))
    except (ValueError, argparse.ArgumentTypeError):
        raise argparse.ArgumentTypeError("thresholds must be comma-separated finite numbers between 0 and 1") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true", help="synthetic illustrative results; no settings, providers, or router downloads")
    modes.add_argument("--real", action="store_true", help="explicitly authorize configured model calls and RouteLLM scoring")
    parser.add_argument("--output", type=Path, default=BACKEND_DIR / "data/calibration")
    parser.add_argument("--catalog", type=Path, default=FIXTURES / "catalog.json")
    parser.add_argument("--cases", type=Path, help="versioned JSON corpus with synthetic=true and cases")
    parser.add_argument("--thresholds", type=threshold_list,
                        help="explicit comma-separated grid; default uses pilot-score midpoints plus 0/1")
    parser.add_argument("--min-pass-rate", type=fraction, default=0.95, help="requested provisional pilot target (default .95)")
    parser.add_argument("--repeats", type=positive, default=1)
    parser.add_argument("--limit", type=positive)
    args = parser.parse_args(argv)
    connection = None
    destination = None
    try:
        payload = json.loads(args.catalog.read_text(encoding="utf-8"))
        connection = catalog_snapshot(payload)
        corpus, references = default_cases(connection, payload)
        if args.cases:
            corpus = json.loads(args.cases.read_text(encoding="utf-8"))
        validate_cases(corpus, payload, connection)
        if args.limit:
            corpus = {**corpus, "cases": corpus["cases"][:args.limit]}
        clients = scorer = None
        settings = None
        config = {"mode": "dry-run", "models": {"small": "simulated-small", "large": "simulated-large"}}
        if args.real:
            # Offline scoring needs a router method, not an already selected threshold.
            # The live app's strict threshold validation remains unchanged.
            settings = Settings(router_mode="mock")
            if settings.model_mode != "real":
                raise ValueError("Real calibration requires MODEL_MODE=real.")
            if settings.routellm_router in OPENAI_ROUTERS and not (
                    settings.openai_api_key and settings.openai_api_key.get_secret_value().strip()):
                raise ValueError("This router requires an OpenAI embeddings key.")
            clients = build_clients(settings)
            scorer = load_routellm_scorer(settings.routellm_router,
                settings.openai_api_key.get_secret_value() if settings.openai_api_key else None)
            if not callable(scorer):
                raise ValueError("A real scoring function is required; no simulated fallback.")
            config = {"mode": "real", "models": {k: {"provider": c.provider, "model": c.model,
                "endpoint_host": urlsplit(settings.ollama_base_url if c.provider == "ollama" else settings.openai_base_url).hostname}
                for k, c in clients.items()},
                "router": settings.routellm_router, "router_config": "GPT_4_AUGMENTED_CONFIG",
                **scorer_metadata(scorer), "model_weight_revisions": None,
                "timeout_seconds": settings.model_timeout_seconds, "agent_max_steps": settings.agent_max_steps}
        packages = {}
        for name in ("routellm", "torch", "transformers"):
            try:
                packages[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                packages[name] = None
        destination = new_run_directory(args.output, "calibration")
        manifest = {"version": VERSION, "purpose": "calibration", "status": "running", "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "catalog_version": payload.get("version"), "catalog_sha256": digest(payload), "corpus_sha256": digest(corpus),
            "configuration": config, "packages": packages, "repeats": args.repeats,
            "thresholds": args.thresholds, "minimum_pass_rate": args.min_pass_rate,
            "oracle_rules": STAGE_CHECKS, "oracle_version": "provisional-stage-pass-v1",
            "model_temperature": 0,
            "revision_note": "Model specs/package versions and exposed router checkpoint identity are recorded. Missing model/router revisions stay unknown; pin and document them before research use."}
        write_json(destination / "manifest.json", manifest)
        write_json(destination / "catalog.json", payload)
        write_json(destination / "contexts.json", corpus)
        rows = []
        scenarios = {s["id"]: s for s in payload["scenarios"]}
        n = len(corpus["cases"]) * args.repeats
        max_steps = settings.agent_max_steps if settings else 4
        print(f"{config['mode']}: {n} contexts; up to {n * 2 * (max_steps + 1)} model calls plus {n} router scorings in real mode.")
        with (destination / "evaluations.jsonl").open("x", encoding="utf-8") as stream:
            for repeat in range(args.repeats):
                for index, case in enumerate(corpus["cases"]):
                    result = evaluate_case(case, index, repeat, connection, scenarios, references, clients, scorer, max_steps)
                    rows.append(result)
                    stream.write(json_text(result) + "\n")
                    stream.flush()
        thresholds = args.thresholds or candidate_thresholds(rows)
        report = calibration_report(rows, thresholds, args.min_pass_rate)
        report["coverage"] = {"scenarios": sorted({r["scenario_id"] for r in rows}),
            "checkpoints": sorted({r["checkpoint"] for r in rows}),
            "holdout_contexts": sum(r["split"] == "holdout" for r in rows)}
        write_json(destination / "report.json", report)
        write_csv(destination / "thresholds.csv", report["thresholds"], ("threshold",))
        write_json(destination / "manifest.json", {**manifest, "status": "complete" if report["complete"] else "completed_with_errors",
            "thresholds": thresholds, "contexts_evaluated": len(rows), "error_contexts": sum(not r["ok"] for r in rows)})
        print(f"Calibration report: {destination}")
        print("Candidate threshold: " + (str(report["recommendation"]["threshold"]) if report["recommendation"] else "none; review errors, quality target, and sample coverage"))
        return 0 if report["complete"] else 1
    except KeyboardInterrupt:
        if destination:
            write_json(destination / "interrupted.json", {"status": "interrupted", "version": VERSION})
        print("Calibration interrupted; completed evaluations remain in the new output directory.")
        return 130
    except Exception as error:
        # Pydantic/provider exception strings can include raw settings; do not print them.
        if destination:
            try:
                write_json(destination / "failure.json", {"status": "failed", "error_type": type(error).__name__})
            except OSError:
                pass
        print(f"Calibration failed ({type(error).__name__}). Check inputs/configuration and optional router dependencies. No participant database was opened.")
        return 1
    finally:
        if connection:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
