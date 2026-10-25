import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
WRAPPERS = ("calibrate.sh", "export-csv.sh")


def project(tmp_path, python=True, real=False):
    root = tmp_path / "project with spaces"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    backend = root / "backend"
    backend.mkdir()
    for name in WRAPPERS:
        (scripts / name).write_text((ROOT / "scripts" / name).read_text())
    if python:
        interpreter = backend / ".venv/bin/python"
        interpreter.parent.mkdir(parents=True)
        if real:
            interpreter.write_text('#!/bin/bash\nexec "$TEST_PYTHON" "$@"\n')
            interpreter.chmod(0o755)
            (backend / "app").symlink_to(ROOT / "backend/app", target_is_directory=True)
        else:
            fake = root / "fake_python.py"
            fake.write_text("import json, os, sys\n"
                "if sys.argv[1:2] == ['-c']:\n"
                "    raise SystemExit(int(os.environ.get('TEST_IMPORT_FAILURE', '0')))\n"
                "print(json.dumps({'cwd': os.getcwd(), 'args': sys.argv[1:]}))\n"
                "raise SystemExit(int(os.environ.get('TEST_EXIT_CODE', '0')))\n")
            interpreter.write_text('#!/bin/bash\nexec "$TEST_PYTHON" "$TEST_FAKE" "$@"\n')
            interpreter.chmod(0o755)
    return root


def run(root, name, args=(), **env):
    return subprocess.run(["bash", str(root / "scripts" / name), *args], cwd=root.parent,
        env={**os.environ, "TEST_PYTHON": sys.executable, "TEST_FAKE": str(root / "fake_python.py"), **env},
        capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize("name", WRAPPERS)
def test_missing_environment_has_setup_guidance_without_installing(tmp_path, name):
    root = project(tmp_path, python=False)
    result = run(root, name)
    assert result.returncode == 1
    assert "bash scripts/setup-all.sh" in result.stderr
    assert not (root / "backend/.venv").exists()


def test_calibration_forwards_modes_and_options_and_propagates_exit_status(tmp_path):
    root = project(tmp_path)
    args = ["--real", "--limit", "2", "--cases", "cases with spaces.json", "--thresholds", ".4,.5"]
    result = run(root, "calibrate.sh", args, TEST_EXIT_CODE="17")
    assert result.returncode == 17
    call = json.loads(result.stdout)
    assert call == {"cwd": str(root / "backend"), "args": ["-m", "app.calibrate", *args]}
    bare = run(root, "calibrate.sh")
    assert json.loads(bare.stdout)["args"] == ["-m", "app.calibrate"]  # No implicit --real or --dry-run.
    help_result = run(root, "calibrate.sh", ["--help"])
    assert json.loads(help_result.stdout)["args"][-1] == "--help"


def test_calibration_checks_core_dependencies_without_loading_the_app(tmp_path):
    root = project(tmp_path)
    result = run(root, "calibrate.sh", ["--real"], TEST_IMPORT_FAILURE="1")
    assert result.returncode == 1 and not result.stdout
    assert "dependencies are missing" in result.stderr
    assert "setup-all.sh" in result.stderr


def test_csv_default_and_override_forwarding_and_exit_status(tmp_path):
    root = project(tmp_path)
    result = run(root, "export-csv.sh")
    assert json.loads(result.stdout) == {"cwd": str(root / "backend"),
        "args": ["-m", "app.export_csv", "--database", str(root / "backend/data/model-matchmakers.sqlite3")]}
    args = ["--database", "other source.sqlite3", "--output", "csv outputs", "--study-only"]
    result = run(root, "export-csv.sh", args, TEST_EXIT_CODE="9")
    assert result.returncode == 9
    assert json.loads(result.stdout)["args"][-len(args):] == args


def test_actual_wrappers_support_help_explicit_dry_run_and_read_only_custom_export(tmp_path):
    root = project(tmp_path, real=True)
    env = {"MODEL_MODE": "invalid", "ROUTER_MODE": "invalid"}
    for name in WRAPPERS:
        result = run(root, name, ["--help"], **env)
        assert result.returncode == 0, result.stderr
        assert "usage:" in result.stdout
    bare = run(root, "calibrate.sh", **env)
    assert bare.returncode == 2 and "--dry-run" in bare.stderr and "--real" in bare.stderr
    dry = run(root, "calibrate.sh", ["--dry-run", "--limit", "1", "--output", "calibration outputs"], **env)
    assert dry.returncode == 0, dry.stdout + dry.stderr
    reports = list((root / "backend/calibration outputs").glob("calibration-*/manifest.json"))
    assert len(reports) == 1 and json.loads(reports[0].read_text())["configuration"]["mode"] == "dry-run"
    source = root / "backend/custom source.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE sessions (id TEXT, state TEXT)")
        connection.execute("INSERT INTO sessions VALUES ('synthetic','{}')")
    before = source.read_bytes()
    exported = run(root, "export-csv.sh", ["--database", "custom source.sqlite3", "--output", "csv outputs"], **env)
    assert exported.returncode == 0, exported.stdout + exported.stderr
    assert source.read_bytes() == before
    manifests = list((root / "backend/csv outputs").glob("export-*/manifest.json"))
    assert len(manifests) == 1
    assert json.loads(manifests[0].read_text())["database"] == str(source)
    assert not (root / "backend/data/model-matchmakers.sqlite3").exists()
    default = root / "backend/data/model-matchmakers.sqlite3"
    default.parent.mkdir()
    with sqlite3.connect(default) as connection:
        connection.execute("CREATE TABLE sessions (id TEXT, state TEXT)")
    default_result = run(root, "export-csv.sh", ["--output", "default csv outputs"], **env)
    assert default_result.returncode == 0, default_result.stdout + default_result.stderr
    manifest = next((root / "backend/default csv outputs").glob("export-*/manifest.json"))
    assert json.loads(manifest.read_text())["database"] == str(default)
