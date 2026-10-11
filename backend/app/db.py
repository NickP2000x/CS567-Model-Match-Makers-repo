"""SQLite storage: the seeded catalog, allocation slots, and one JSON state per session."""

import json
import random
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .definitions import FIXTURES

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS catalog_scenarios (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS catalog_items (
  id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, category TEXT NOT NULL,
  position INTEGER NOT NULL, data TEXT NOT NULL
);
-- Twelve pre-shuffled slots, three per sequence (paper plan: 12 participants).
CREATE TABLE IF NOT EXISTS allocation_slots (
  slot INTEGER PRIMARY KEY, sequence_id INTEGER NOT NULL, session_id TEXT UNIQUE
);
-- The whole participant-visible study state is stored as JSON, matching the frontend shape.
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, participant_id TEXT NOT NULL, sequence_id INTEGER NOT NULL,
  development INTEGER NOT NULL, state TEXT NOT NULL,
  created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
-- Research record of every real model call (#35/#38). Never served to participants.
-- `shown` is 0 when the reply was discarded because the task or checkpoint had moved on.
CREATE TABLE IF NOT EXISTS model_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, task_id TEXT NOT NULL,
  checkpoint TEXT NOT NULL, size TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
  step INTEGER NOT NULL, ok INTEGER NOT NULL, error TEXT, prompt_tokens INTEGER,
  completion_tokens INTEGER, latency_ms INTEGER NOT NULL, tools TEXT NOT NULL,
  shown INTEGER NOT NULL, created_at INTEGER NOT NULL
);
"""
SLOTS_PER_SEQUENCE = 3


def connect(path: Path) -> sqlite3.Connection:
    # Autocommit mode; transactions are opened explicitly with BEGIN IMMEDIATE.
    connection = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def transaction(path: Path) -> Iterator[sqlite3.Connection]:
    """One write-locked transaction per request, so state changes never interleave."""
    connection = connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()


def init_db(path: Path) -> None:
    """Create tables, (re)seed the catalog, and create allocation slots once. Safe to repeat."""
    path.parent.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((FIXTURES / "catalog.json").read_text(encoding="utf-8"))
    connection = connect(path)
    try:
        connection.executescript(SCHEMA)
    finally:
        connection.close()
    with transaction(path) as connection:
        connection.execute("DELETE FROM catalog_scenarios")
        connection.execute("DELETE FROM catalog_items")
        connection.executemany("INSERT INTO catalog_scenarios (id, data) VALUES (?, ?)",
                               [(s["id"], json.dumps(s)) for s in catalog["scenarios"]])
        connection.executemany(
            "INSERT INTO catalog_items (id, scenario_id, category, position, data) VALUES (?, ?, ?, ?, ?)",
            [(item["id"], item["scenarioId"], item["category"], position, json.dumps(item))
             for position, item in enumerate(catalog["items"])])
        connection.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('catalog_version', ?)",
                           (catalog["version"],))
        if connection.execute("SELECT COUNT(*) FROM allocation_slots").fetchone()[0] == 0:
            sequences = [sequence for sequence in (1, 2, 3, 4) for _ in range(SLOTS_PER_SEQUENCE)]
            random.SystemRandom().shuffle(sequences)
            connection.executemany("INSERT INTO allocation_slots (slot, sequence_id) VALUES (?, ?)",
                                   list(enumerate(sequences, start=1)))
