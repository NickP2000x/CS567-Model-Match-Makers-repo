"""Small file/snapshot helpers for researcher-only command-line tools."""

import csv
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def write_json(path: Path, value) -> None:
    path.write_text(json_text(value) + "\n", encoding="utf-8")


def new_run_directory(parent: Path, prefix: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    name = prefix + datetime.now(timezone.utc).strftime("-%Y%m%dT%H%M%S.%fZ")
    path = parent / name
    path.mkdir()  # Never overwrite a previous run.
    return path


@contextmanager
def read_snapshot(path: Path):
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        yield connection
    finally:
        connection.close()


def csv_value(value):
    # Distinguish NULL from empty text, including literal strings beginning with \.
    if value is None:
        return "\\N"
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list)):
        return json_text(value)
    if isinstance(value, str) and value.startswith("\\"):
        return "\\" + value
    return value


def write_csv(path: Path, rows: list[dict], base_columns=()) -> list[str]:
    columns = list(dict.fromkeys([*base_columns, *sorted({key for row in rows for key in row})]))
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: csv_value(row.get(key)) for key in columns} for row in rows)
    return columns
