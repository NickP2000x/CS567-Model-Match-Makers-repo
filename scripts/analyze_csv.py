#!/usr/bin/env python3
"""Describe one Model Matchmakers CSV snapshot without loading the app or providers.

Run with Python 3.10+: python3 scripts/analyze_csv.py --input EXPORT --output RESULTS
The output argument is a parent directory; each run creates a new analysis-* folder.
"""

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

VERSION = "csv-descriptive-analysis-v1"
CONDITIONS = ("automatic", "override")
CONSTRAINTS = ("budget", "capacity", "dietary", "accessibility", "supplies", "location")
DIMENSIONS = ("mentalDemand", "physicalDemand", "temporalDemand", "performance", "effort", "frustration")
SOURCES = {
    "sessions": ("session_id",),
    "tasks": ("session_id", "task_id"),
    "checkpoint_choices": ("session_id", "task_id", "checkpoint"),
    "model_calls": ("id",),
    "routing_decisions": ("id",),
    "oracle_results": ("routing_id",),
}
REQUIRED = {
    "sessions": {"session_id", "development", "consent"},
    "tasks": {"session_id", "task_id", "condition", "status"},
    "checkpoint_choices": {"session_id", "task_id", "checkpoint", "final_model"},
    "model_calls": {"id", "session_id", "task_id", "purpose", "size"},
    "routing_decisions": {"id", "session_id", "task_id", "checkpoint", "ok", "applied"},
    "oracle_results": {"routing_id", "session_id", "task_id", "checkpoint", "label"},
}
STAT_COLUMNS = ("n", "mean", "sd", "median", "q1", "q3", "minimum", "maximum")


class AnalysisError(ValueError):
    """An input problem, reported without participant values or exception bodies."""


def value(raw):
    if raw is None or raw == "\\N" or raw == "":
        return None
    return raw[1:] if raw.startswith("\\\\") else raw


def boolean(raw):
    if raw is None:
        return None
    return {"1": True, "0": False, "true": True, "false": False}.get(str(raw).lower())


def number(raw):
    try:
        result = float(raw)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def object_value(raw):
    if raw is None:
        return None
    try:
        result = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return result if isinstance(result, dict) else None


def quantile(values, fraction):
    """Linear interpolation at (n - 1) * p (Hyndman-Fan type 7)."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def describe(values):
    if not values:
        return dict.fromkeys(STAT_COLUMNS, None) | {"n": 0}
    return {"n": len(values), "mean": statistics.mean(values),
            "sd": statistics.stdev(values) if len(values) > 1 else None,
            "median": statistics.median(values), "q1": quantile(values, .25),
            "q3": quantile(values, .75), "minimum": min(values), "maximum": max(values)}


def load_snapshot(directory):
    data, hashes, duplicates, missing = {}, {}, {}, []
    for name, keys in SOURCES.items():
        path = directory / (name + ".csv")
        if not path.is_file():
            if name in ("sessions", "tasks"):
                raise AnalysisError(f"Required file is missing: {name}.csv")
            data[name] = None
            missing.append(name + ".csv")
            continue
        content = path.read_bytes()
        hashes[path.name] = hashlib.sha256(content).hexdigest()
        try:
            text = content.decode("utf-8-sig")
            reader = csv.DictReader(text.splitlines(keepends=True), strict=True)
            fields = reader.fieldnames or []
            if len(set(fields)) != len(fields) or not REQUIRED[name].issubset(fields):
                raise AnalysisError(f"Invalid or missing required headers: {name}.csv")
            unique, count = {}, 0
            for line in reader:
                if None in line or any(item is None for item in line.values()):
                    raise AnalysisError(f"Malformed CSV row: {name}.csv")
                row = {key: value(item) for key, item in line.items()}
                key = tuple(row.get(field) for field in keys)
                if any(item is None for item in key):
                    raise AnalysisError(f"Missing row identifier: {name}.csv")
                if key in unique:
                    if unique[key] != row:
                        raise AnalysisError(f"Conflicting duplicate identifiers: {name}.csv. Use one export snapshot.")
                    count += 1
                else:
                    unique[key] = row
            data[name] = list(unique.values())
            duplicates[name] = count
        except (UnicodeError, csv.Error):
            raise AnalysisError(f"Cannot decode CSV: {name}.csv") from None
    manifest = None
    path = directory / "manifest.json"
    if path.is_file():
        content = path.read_bytes()
        hashes[path.name] = hashlib.sha256(content).hexdigest()
        try:
            manifest = json.loads(content)
        except (UnicodeError, ValueError):
            raise AnalysisError("Cannot decode manifest.json") from None
        if not isinstance(manifest, dict):
            raise AnalysisError("manifest.json must contain an object")
        if manifest.get("status") != "complete":
            raise AnalysisError("The export manifest is not complete. Use a completed export.")
        if not isinstance(manifest.get("exported_counts", {}), dict):
            raise AnalysisError("Invalid exported_counts in manifest.json")
        for name, rows in data.items():
            expected = manifest.get("exported_counts", {}).get(name)
            if rows is not None and expected is not None and expected != len(rows) + duplicates[name]:
                raise AnalysisError(f"Manifest row count does not match: {name}.csv")
    return data, {"input_sha256": hashes, "identical_duplicates_removed": duplicates,
                  "missing_optional_files": missing,
                  "export_version": manifest.get("version") if manifest else None,
                  "catalog_version": manifest.get("catalog_version") if manifest else None,
                  "manifest_present": manifest is not None}


def constraint_values(row, warnings):
    saved = object_value(row.get("constraints_json"))
    if saved is not None:
        keys = tuple(name for name in CONSTRAINTS if name in saved)
        # Never guess a missing/partial definition or treat null as failure.
        if not set(CONSTRAINTS[:4]).issubset(keys) or any(type(saved[k]) is not bool for k in keys):
            warnings["invalid_constraint_results"] += 1
            return None
        if any(key not in CONSTRAINTS for key in saved):
            warnings["unknown_constraint_names"] += 1
            return None
        for key in keys:
            raw = row.get("constraint_" + key)
            if raw is not None and boolean(raw) != saved[key]:
                warnings["inconsistent_constraint_columns"] += 1
                return None
    else:
        keys = tuple(key for key in CONSTRAINTS if row.get("constraint_" + key) is not None)
        if keys != CONSTRAINTS:
            warnings["unknown_constraint_definition"] += 1
            return None
        saved = {key: boolean(row.get("constraint_" + key)) for key in keys}
        if any(item is None for item in saved.values()):
            warnings["invalid_constraint_results"] += 1
            return None
    count, passed = sum(saved[key] for key in keys), int(all(saved[key] for key in keys))
    if row.get("constraints_satisfied") is not None and number(row["constraints_satisfied"]) != count:
        warnings["inconsistent_constraint_totals"] += 1
        return None
    if row.get("all_met") is not None and boolean(row["all_met"]) != bool(passed):
        warnings["inconsistent_all_met"] += 1
        return None
    return keys, count, passed


def workload_value(row, warnings):
    score = number(row.get("survey_raw_score"))
    if row.get("survey_submitted_at_ms") is None:
        warnings["ended_tasks_without_submitted_workload"] += 1
        return None
    if score is None:
        warnings["submitted_workload_without_finite_score"] += 1
        return None
    version = row.get("survey_version")
    if version is None or not 0 <= score <= 100:
        warnings["invalid_or_unversioned_workload"] += 1
        return None
    metadata = object_value(row.get("survey_metadata_json"))
    answers = object_value(row.get("survey_answers_json"))
    if metadata is None or answers is None:
        warnings["workload_not_independently_checked_missing_metadata"] += 1
        return version, score
    try:
        low, high, increment = (float(metadata[key]) for key in ("min", "max", "increment"))
        if not all(math.isfinite(v) for v in (low, high, increment)) or high <= low or increment <= 0:
            raise ValueError
        oriented = []
        for key in DIMENSIONS:
            answer = answers[key]
            if type(answer) not in (int, float) or not math.isfinite(answer) or not low <= answer <= high:
                raise ValueError
            if not math.isclose((answer - low) / increment, round((answer - low) / increment), abs_tol=1e-7):
                raise ValueError
            orientation = metadata["items"][key]["orientation"]
            if orientation not in ("higher-is-more-workload", "lower-is-more-workload"):
                raise ValueError
            common = 100 * (answer - low) / (high - low)
            oriented.append(common if orientation == "higher-is-more-workload" else 100 - common)
        if metadata.get("version") != version or not math.isclose(statistics.mean(oriented), score, abs_tol=1e-6):
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError):
        warnings["workload_score_or_metadata_mismatch"] += 1
        return None
    return version, score


def analyze(data, provenance, include_development=False):
    warnings, excluded = Counter(), Counter()
    sessions = {row["session_id"]: row for row in data["sessions"]}
    eligible, identities = {}, {}
    for sid, row in sessions.items():
        development = boolean(row.get("development"))
        if boolean(row.get("consent")) is not True:
            excluded["sessions_without_recorded_consent"] += 1
        elif development is None:
            excluded["sessions_with_unknown_development_status"] += 1
        elif development and not include_development:
            excluded["development_sessions"] += 1
        else:
            eligible[sid] = row
            identity = row.get("prolific_id") or row.get("participant_id") or sid
            if identity in identities:
                raise AnalysisError("An included participant identifier occurs in multiple sessions. Resolve repeat sessions before analysis.")
            identities[identity] = sid

    tasks, per_participant, units = {}, defaultdict(dict), {}
    available_conditions, ended_conditions = defaultdict(set), defaultdict(set)
    status_counts, condition_counts = Counter(), Counter()
    constraint_definitions, survey_versions = Counter(), Counter()

    def record(sid, condition, metric, observation, unit):
        if observation is not None and math.isfinite(observation):
            per_participant[(sid, condition)][metric] = observation
            units[metric] = unit

    for row in data["tasks"]:
        sid, tid, condition = row["session_id"], row["task_id"], row.get("condition")
        if sid not in sessions:
            warnings["orphan_task_rows"] += 1
            continue
        if sid not in eligible:
            continue
        if tid == "practice" or condition == "practice" or boolean(row.get("practice")) is True:
            excluded["practice_tasks"] += 1
            continue
        if tid not in ("task-1", "task-2"):
            excluded["unknown_experimental_task_ids"] += 1
            continue
        if boolean(row.get("excluded_from_results")) is True:
            excluded["tasks_marked_excluded"] += 1
            continue
        if condition not in CONDITIONS:
            excluded["tasks_with_unknown_condition"] += 1
            continue
        if condition in available_conditions[sid]:
            raise AnalysisError("More than one experimental task has the same condition in a session. Resolve this before analysis.")
        available_conditions[sid].add(condition)
        status = row.get("status")
        status_counts[f"{condition}:{status}"] += 1
        condition_counts[condition] += 1
        if status not in ("submitted", "timed-out"):
            excluded["unfinished_experimental_tasks"] += 1
            continue
        start, end = number(row.get("started_at_ms")), number(row.get("ended_at_ms"))
        if start is None or end is None or end < start:
            excluded["ended_tasks_with_invalid_timestamps"] += 1
            continue
        tasks[(sid, tid)] = row
        ended_conditions[sid].add(condition)
        elapsed = (end - start) / 1000
        exported_elapsed = number(row.get("elapsed_seconds"))
        if exported_elapsed is not None and not math.isclose(exported_elapsed, elapsed, abs_tol=.001):
            warnings["elapsed_column_mismatch_using_timestamps"] += 1
        deadline = number(row.get("deadline_ms"))
        if deadline is not None and end > deadline:
            warnings["tasks_ended_after_original_deadline"] += 1
        record(sid, condition, "elapsed_seconds", elapsed, "seconds to submission or timeout")
        if status == "submitted":
            record(sid, condition, "submitted_elapsed_seconds", elapsed, "seconds; submitted tasks only")
        record(sid, condition, "timed_out", int(status == "timed-out"), "proportion of ended tasks")
        constraints = constraint_values(row, warnings)
        if constraints:
            keys, count, all_met = constraints
            definition = "+".join(keys)
            constraint_definitions[definition] += 1
            record(sid, condition, "constraints_satisfied:" + definition, count, f"constraints out of {len(keys)}")
            record(sid, condition, "all_met:" + definition, all_met, "proportion of ended tasks")
        workload = workload_value(row, warnings)
        if workload:
            version, score = workload
            survey_versions[version] += 1
            record(sid, condition, "workload:" + version, score, "versioned workload score, 0-100")

    task_keys = set(tasks)
    by_task = {}
    for name in ("checkpoint_choices", "model_calls"):
        grouped = defaultdict(list)
        for row in data[name] or []:
            key = (row.get("session_id"), row.get("task_id"))
            if row.get("session_id") not in sessions:
                warnings["orphan_" + name + "_rows"] += 1
            if key in task_keys:
                grouped[key].append(row)
        by_task[name] = grouped

    usage = Counter()
    model_names, routing_settings = Counter(), Counter()
    route_counts = {condition: Counter() for condition in CONDITIONS}
    choices_by_key = {}
    for key, row in tasks.items():
        sid, _ = key
        condition = row["condition"]
        counts = route_counts[condition]
        choices = by_task["checkpoint_choices"][key]
        committed = [c for c in choices if c.get("phase") == "committed" and c.get("final_model") in ("small", "large")]
        if data["checkpoint_choices"] is not None:
            counts["reached_checkpoint_rows"] += len(choices)
            counts["committed_choices"] += len(committed)
            counts["final_large_choices"] += sum(c["final_model"] == "large" for c in committed)
        if committed:
            record(sid, condition, "final_large_choice_rate", sum(c["final_model"] == "large" for c in committed) / len(committed), "per-participant checkpoint proportion")
        for choice in choices:
            choices_by_key[(*key, choice["checkpoint"])] = choice
        if condition == "override":
            for metric, field in (("override_recommendation_rate", "recommended_model"),
                                  ("initial_choice_change_rate", "initial_model")):
                known = [c for c in committed if c.get(field) in ("small", "large")]
                numerator = sum(c[field] != c["final_model"] for c in known)
                if data["checkpoint_choices"] is not None:
                    counts[metric + "_numerator"] += numerator
                    counts[metric + "_denominator"] += len(known)
                if known:
                    record(sid, condition, metric, numerator / len(known), "per-participant checkpoint proportion")
            for field in ("initial_choice_ms", "post_recommendation_ms", "decision_total_ms"):
                values = [number(c.get(field)) for c in committed]
                if any(v is not None and v < 0 for v in values):
                    warnings["negative_choice_intervals"] += 1
                values = [v / 1000 for v in values if v is not None and v >= 0]
                if values:
                    record(sid, condition, "mean_" + field.replace("_ms", "_seconds"), statistics.mean(values), "seconds; participant mean across known choices")

        if data["model_calls"] is not None:
            all_calls = by_task["model_calls"][key]
            for call in all_calls:
                purpose = call.get("purpose")
                usage["oracle_calls" if purpose == "oracle" else "unknown_purpose_calls" if purpose != "participant" else "participant_calls"] += 1
            calls = [c for c in all_calls if c.get("purpose") == "participant"]
            if any(c.get("purpose") not in ("participant", "oracle") for c in all_calls):
                warnings["unknown_call_purpose_usage_incomplete"] += 1
            else:
                record(sid, condition, "participant_model_calls", len(calls), "calls, including failed or unshown calls")
                if all(c.get("size") in ("small", "large") for c in calls):
                    record(sid, condition, "participant_large_model_calls", sum(c["size"] == "large" for c in calls), "calls")
                for field in ("prompt_tokens", "completion_tokens"):
                    values = [number(c.get(field)) for c in calls]
                    if all(v is not None and v >= 0 and v.is_integer() for v in values):
                        record(sid, condition, "participant_" + field, sum(values), "tokens")
                    else:
                        warnings["tasks_with_incomplete_" + field] += 1
                if all(boolean(c.get("ok")) is not None for c in calls):
                    record(sid, condition, "participant_failed_calls", sum(boolean(c["ok"]) is False for c in calls), "calls")
            for call in calls:
                usage["participant_failed_calls"] += boolean(call.get("ok")) is False
                usage["participant_unshown_calls"] += boolean(call.get("shown")) is False
                if call.get("model"):
                    model_names[call["model"]] += 1

    # Join only unambiguous, successful applied routes to their exact offline result.
    applied = defaultdict(list)
    for route in data["routing_decisions"] or []:
        key = (route.get("session_id"), route.get("task_id"))
        if key not in task_keys:
            continue
        counts = route_counts[tasks[key]["condition"]]
        counts["routing_attempts"] += 1
        if boolean(route.get("ok")) is False:
            counts["routing_errors"] += 1
        if boolean(route.get("ok")) is True and boolean(route.get("applied")) is True:
            applied[(*key, route["checkpoint"])].append(route)
            routing_settings[json.dumps({"router": route.get("router"), "threshold": route.get("threshold")}, sort_keys=True)] += 1
    oracles = {row["routing_id"]: row for row in data["oracle_results"] or []}
    agreement = defaultdict(list)
    for key, routes in applied.items():
        condition = tasks[key[:2]]["condition"]
        counts = route_counts[condition]
        counts["applied_routes"] += len(routes)
        if len(routes) != 1:
            warnings["ambiguous_applied_routes_at_checkpoint"] += 1
            continue
        route = routes[0]
        outcome = oracles.get(route["id"])
        if outcome is None:
            counts["routes_without_oracle_result"] += 1
            continue
        if any(outcome.get(field) != route.get(field) for field in ("session_id", "task_id", "checkpoint")):
            warnings["oracle_route_context_mismatch"] += 1
            continue
        small, large = boolean(outcome.get("small_passed")), boolean(outcome.get("large_passed"))
        label = "small" if small else "large" if large else "neither"
        if small is None or large is None or outcome.get("label") != label:
            warnings["inconsistent_oracle_labels"] += 1
            continue
        counts["valid_oracle_results"] += 1
        if label == "neither":
            counts["oracle_neither_passes"] += 1
            continue
        choice = choices_by_key.get(key)
        if choice and choice.get("phase") == "committed" and choice.get("final_model") in ("small", "large"):
            match = int(choice["final_model"] == label)
            counts["final_oracle_agreement_numerator"] += match
            counts["final_oracle_agreement_denominator"] += 1
            agreement[(key[0], condition)].append(match)
    for (sid, condition), observations in agreement.items():
        record(sid, condition, "oracle_preferred_choice_agreement", statistics.mean(observations), "per-participant proportion; neither excluded")

    summary, pairs = [], []
    for metric in sorted(units):
        for condition in CONDITIONS:
            observations = [values[metric] for (sid, c), values in per_participant.items() if c == condition and metric in values]
            binary = metric == "timed_out" or metric.startswith("all_met:")
            summary.append({"metric": metric, "unit": units[metric], "condition": condition, **describe(observations),
                            "events": int(sum(observations)) if observations and binary else None,
                            "event_rate": statistics.mean(observations) if observations and binary else None})
        differences = [per_participant[(sid, "override")][metric] - per_participant[(sid, "automatic")][metric]
                       for sid in eligible if metric in per_participant[(sid, "automatic")]
                       and metric in per_participant[(sid, "override")]]
        pairs.append({"metric": metric, "unit": units[metric], "direction": "override minus automatic", **describe(differences)})

    sequence_counts = Counter(row.get("sequence_id") or "unknown" for row in eligible.values())
    for source in ("model_calls", "routing_decisions", "oracle_results"):
        warnings["orphan_" + source + "_rows"] = sum(row.get("session_id") not in sessions for row in data[source] or [])
    simulation = Counter()
    for row in eligible.values():
        for field in ("simulated", "router_simulated"):
            state = boolean(row.get(field))
            simulation[field + ":" + ("unknown" if state is None else str(state).lower())] += 1
    if len(constraint_definitions) > 1:
        warnings["mixed_constraint_definitions_reported_separately"] += 1
    if len(survey_versions) > 1:
        warnings["mixed_survey_versions_reported_separately"] += 1
    if len(routing_settings) > 1:
        warnings["mixed_routing_settings"] += 1
    if len(model_names) > 2:
        warnings["more_than_two_model_identifiers"] += 1
    report = {"version": VERSION, **provenance,
              "include_development": include_development,
              "counts": {"exported_sessions": len(sessions), "included_sessions": len(eligible),
                         "sessions_with_both_ended_conditions": sum(len(c) == 2 for c in ended_conditions.values()),
                         "sessions_without_both_ended_conditions": len(eligible) - sum(len(c) == 2 for c in ended_conditions.values()),
                         "included_ended_tasks": len(tasks), "session_steps": dict(Counter(r.get("step") or "unknown" for r in eligible.values())),
                         "sequence_counts": dict(sequence_counts),
                         "both_ended_sequence_counts": dict(Counter(eligible[sid].get("sequence_id") or "unknown" for sid, c in ended_conditions.items() if len(c) == 2)),
                         "available_experimental_tasks_by_condition": dict(condition_counts),
                         "task_status_counts": dict(status_counts)},
              "exclusions": dict(excluded), "warnings": {k: v for k, v in warnings.items() if v},
              "constraint_definitions": dict(constraint_definitions), "survey_versions": dict(survey_versions),
              "simulation_flags": dict(simulation), "participant_model_identifiers": dict(model_names),
              "routing_settings": [json.loads(k) | {"applied_routes": v} for k, v in routing_settings.items()],
              "call_accounting_for_included_ended_tasks": dict(usage),
              "methods": [
                  "Descriptive statistics only; no hypothesis tests, p-values, or causal/significance claims.",
                  "One ended task per participant and condition. Paired differences use both nonmissing values for the same metric.",
                  "Quartiles use linear interpolation at (n-1)*p (type 7). SD is the sample SD and is missing for n<2.",
                  "Elapsed task time includes submitted and timed-out tasks; it is not uncensored time to successful completion. Submitted-only elapsed is separate.",
                  "Stored final end minus initial start includes wall time between submission and reopening. No timestamps are rewritten.",
                  "Constraint definitions and workload versions are separate metrics; earlier results are never rescored with current rules.",
                  "Saved workload scores are used; available six-response metadata is checked, including performance orientation.",
                  "Calls include failed and unshown participant-purpose requests. Oracle and unknown-purpose calls are excluded from participant usage.",
                  "Unknown token usage is not zero. Zero calls/tokens is reported only when the call file is available and its task purpose is known.",
                  "Checkpoint rates are averaged within each participant before condition summaries. Pooled checkpoint counts are descriptive, not independent sample sizes.",
                  "Oracle agreement uses the preferred-size label, excludes neither-passes outcomes, and is not a validated appropriate-reliance measure.",
                  "Results describe this export, not verified recruitment, eligibility, ethics approval, or validated router calibration.",
              ]}
    routing = [{"condition": condition, "choices_file_available": data["checkpoint_choices"] is not None,
                "routing_file_available": data["routing_decisions"] is not None,
                "oracle_file_available": data["oracle_results"] is not None,
                **dict(route_counts[condition])} for condition in CONDITIONS]
    return summary, pairs, routing, report


def display(raw):
    return "--" if raw is None else f"{raw:.2f}" if isinstance(raw, (int, float)) else str(raw)


def latex(raw):
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
                    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(char, char) for char in str(raw))


def median_iqr(row):
    return "--" if not row["n"] else f"{display(row['median'])} [{display(row['q1'])}, {display(row['q3'])}]"


def condition_cell(row):
    if row.get("events") is not None:
        return f"{row['events']}/{row['n']} ({100 * row['event_rate']:.1f}%)"
    return median_iqr(row)


def metric_label(metric):
    if metric.startswith("constraints_satisfied:"):
        return f"Constraints satisfied ({len(metric.split(':', 1)[1].split('+'))} checks)"
    if metric.startswith("all_met:"):
        return f"All constraints satisfied ({len(metric.split(':', 1)[1].split('+'))} checks)"
    if metric.startswith("workload:"):
        return "Workload score (" + metric.split(":", 1)[1] + ")"
    return metric.replace("_", " ").capitalize()


def paper_outputs(summary, pairs, report):
    rows = defaultdict(dict)
    for row in summary:
        rows[row["metric"]][row["condition"]] = row
    paired = {row["metric"]: row for row in pairs}
    table = [r"% Generated descriptive summaries. Review units, versions and denominators before submission."]
    # Short separate tables avoid one very long or over-wide table in an ACM column.
    for metric, conditions in rows.items():
        binary = metric == "timed_out" or metric.startswith("all_met:")
        table += [r"\begin{table}[t]", r"\centering", r"\small",
                  r"\caption{" + latex(metric_label(metric)) + ". " +
                  ("Condition rows show events/total (percent). The paired difference shows median [Q1, Q3]. " if binary else "Median [Q1, Q3]. ") +
                  latex(conditions["automatic"]["unit"]) + ".}",
                  r"\begin{tabular}{lrl}", r"\hline", r"Condition & $n$ & Summary \\", r"\hline"]
        for condition in CONDITIONS:
            row = conditions[condition]
            table.append(f"{condition.title()} & {row['n']} & {latex(condition_cell(row))}" + r" \\")
        pair = paired[metric]
        table += [f"Override $-$ Automatic & {pair['n']} & {latex(median_iqr(pair))}" + r" \\",
                  r"\hline", r"\end{tabular}", r"\end{table}", ""]
    counts = report["counts"]
    text = ["# Descriptive Results draft", "", "Review this draft against the study protocol before using it in the paper.", "",
            "## Sample and completeness", "",
            f"The export contained {counts['exported_sessions']} sessions. The stated inclusion rules retained "
            f"{counts['included_sessions']} sessions and {counts['included_ended_tasks']} ended experimental tasks. "
            f"Both experimental conditions had ended in {counts['sessions_with_both_ended_conditions']} sessions. "
            "These are session counts; recruitment, repeat participation and exclusions must be confirmed by the researchers.", "",
            f"Development sessions {'were explicitly included' if report['include_development'] else 'were excluded'}. "
            "Practice and explicitly excluded tasks were omitted. Unfinished tasks did not contribute final outcomes. "
            "Timed-out tasks contributed their saved outcomes and elapsed time, with timeouts reported separately.", "",
            "## Analysis method", "",
            "We used descriptive statistics. Numerical outcomes were summarized by condition using medians and "
            "interquartile ranges. We calculated within-participant differences as Override minus Automatic when "
            "both values were available for the same measure and version. Quartiles used linear interpolation "
            "(type 7). Binary outcomes are also shown as counts and percentages. Each measure reports its own sample size. Checkpoints and model calls were not treated as "
            "independent participants. No hypothesis tests were performed.", "",
            "## Observed summaries", "",
            "Proportion metrics range from 0 to 1. Multiply by 100 to express a proportion as a percentage. "
            "Oracle agreement is preferred-size agreement, not proof of appropriate reliance.", ""]
    for metric, conditions in rows.items():
        auto, over, pair = conditions["automatic"], conditions["override"], paired[metric]
        # JSON escaping prevents arbitrary version text from becoming Markdown formatting.
        label = json.dumps(metric_label(metric), ensure_ascii=True)
        text.append(f"- {label}: Automatic {condition_cell(auto)} (n={auto['n']}); "
                    f"Override {condition_cell(over)} (n={over['n']}); paired difference "
                    f"{median_iqr(pair)} (paired n={pair['n']}). Unit: {auto['unit']}.")
    text += ["", "## Before submission / analysis still to complete", "",
             "- Confirm unique participants, actual recruitment, condition order, inclusion rules and missing data.",
             "- Review data_quality_report.json, all warning counts, model identifiers and routing settings.",
             "- Confirm the implemented catalog, constraint and workload versions match the collected study.",
             "- Review oracle coverage before making claims about recommendation suitability or reliance.",
             "- Select relevant tables from paper_tables.tex; do not paste every supplemental measure by default.",
             "- Add actual collection details to the past-tense Method. Do not claim statistical significance or a calibrated threshold from these summaries."]
    if not rows:
        text += ["", "No eligible ended tasks supplied numerical outcomes. No condition findings can be reported."]
    return "\n".join(table) + "\n", "\n".join(text) + "\n"


def write_outputs(parent, summary, pairs, routing, report):
    parent.mkdir(parents=True, exist_ok=True)
    directory = parent / ("analysis-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"))
    directory.mkdir()
    outputs = (("condition_summary.csv", summary, ("metric", "unit", "condition", *STAT_COLUMNS)),
               ("paired_comparisons.csv", pairs, ("metric", "unit", "direction", *STAT_COLUMNS)),
               ("routing_summary.csv", routing, ("condition",)))
    for name, rows, base in outputs:
        columns = list(dict.fromkeys([*base, *sorted({key for row in rows for key in row})]))
        with (directory / name).open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows({key: row.get(key) if row.get(key) is not None else "\\N" for key in columns} for row in rows)
    tex, text = paper_outputs(summary, pairs, report)
    (directory / "paper_tables.tex").write_text(tex, encoding="utf-8")
    (directory / "results_summary.md").write_text(text, encoding="utf-8")
    (directory / "data_quality_report.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return directory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="one CSV export folder, not a parent containing multiple exports")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "backend/data/analysis", help="parent for a new analysis-* output folder")
    parser.add_argument("--include-development", action="store_true", help="explicitly include development sessions and label the report accordingly")
    args = parser.parse_args(argv)
    try:
        source, parent = args.input.resolve(), args.output.resolve()
        if not source.is_dir():
            raise AnalysisError("The input must be an existing CSV export directory.")
        if parent == source or source in parent.parents:
            raise AnalysisError("The output parent must be outside the source export directory.")
        data, provenance = load_snapshot(source)
        summary, pairs, routing, report = analyze(data, provenance, args.include_development)
        # Detect edits during analysis rather than reporting a mixture of snapshots.
        if any(hashlib.sha256((source / name).read_bytes()).hexdigest() != digest for name, digest in provenance["input_sha256"].items()):
            raise AnalysisError("An input file changed during analysis. Retry with a frozen export.")
        directory = write_outputs(parent, summary, pairs, routing, report)
        print(f"Analysis outputs: {directory}")
        print(f"Included sessions: {report['counts']['included_sessions']}; both conditions ended: {report['counts']['sessions_with_both_ended_conditions']}")
        print(f"Warning categories: {len(report['warnings'])}. Review data_quality_report.json before using the tables.")
        if not report["counts"]["included_ended_tasks"]:
            print("No eligible ended experimental tasks. Check the inclusion rules and development flags.")
            return 2
        return 0
    except AnalysisError as error:
        print(f"Analysis input error: {error}", file=sys.stderr)
        return 2
    except OSError:
        print("Analysis file error. Check input access and output permissions; no provider calls were made.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
