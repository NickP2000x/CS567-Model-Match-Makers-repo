"""Session persistence: allocation, loading, and saving one JSON state per request."""

import json
import secrets
import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from . import db
from .errors import ApiError
from .study import TaskExpired, new_state

T = TypeVar("T")


def system_clock() -> int:
    return int(time.time() * 1000)


class Store:
    def __init__(self, path: Path, clock: Callable[[], int] = system_clock, simulated: bool = True,
                 router_simulated: bool = True):
        self.path = path
        self.clock = clock
        # New sessions report whether agent replies are simulated (mock mode) or real.
        self.simulated = simulated
        self.router_simulated = router_simulated
        self._ready = False
        self._lock = threading.Lock()

    def _ensure_ready(self) -> None:
        with self._lock:
            if not self._ready:
                db.init_db(self.path)
                self._ready = True

    def read(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        """Run a read-only query (catalog) on a short-lived connection."""
        self._ensure_ready()
        connection = db.connect(self.path)
        try:
            return operation(connection)
        finally:
            connection.close()

    def create_session(self, sequence_id: int | None = None) -> dict:
        """Allocate the next shuffled slot, or create a development session for a chosen sequence."""
        self._ensure_ready()
        session_id = secrets.token_hex(16)
        now = self.clock()
        with db.transaction(self.path) as connection:
            if sequence_id is None:
                slot = connection.execute(
                    "SELECT slot, sequence_id FROM allocation_slots WHERE session_id IS NULL ORDER BY slot LIMIT 1"
                ).fetchone()
                if slot is None:
                    raise ApiError(409, "ALLOCATION_FULL", "All study slots are allocated.")
                state = new_state(session_id, f"P{slot['slot']:02d}", slot["sequence_id"], self.simulated, self.router_simulated)
                connection.execute("UPDATE allocation_slots SET session_id = ? WHERE slot = ?",
                                   (session_id, slot["slot"]))
            else:
                # Development sessions never consume allocation slots.
                state = new_state(session_id, f"dev-{session_id[:8]}", sequence_id, self.simulated, self.router_simulated)
            connection.execute(
                "INSERT INTO sessions (id, participant_id, sequence_id, development, state, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, state["participantId"], state["sequenceId"], int(sequence_id is not None),
                 json.dumps(state), now, now))
        return state

    def get_state(self, session_id: str) -> dict:
        self._ensure_ready()
        return self.read(lambda connection: load(connection, session_id))

    def mutate(self, session_id: str, operation: Callable[[sqlite3.Connection, dict, int], T]) -> tuple[T, dict]:
        """Apply one operation atomically. Failures leave stored state unchanged,
        except a deadline expiry, which is saved before TASK_EXPIRED is returned."""
        self._ensure_ready()
        expired = None
        with db.transaction(self.path) as connection:
            state = load(connection, session_id)
            now = self.clock()
            try:
                result = operation(connection, state, now)
            except TaskExpired:
                result, expired = None, state
            save(connection, session_id, state, now)
        if expired is not None:
            raise ApiError(409, "TASK_EXPIRED", "The task deadline has passed.", state=expired)
        return result, state


    def record_model_calls(self, session_id: str, task_id: str, checkpoint: str, size: str,
                           provider: str, model: str, calls: list, shown: bool,
                           purpose: str = "participant") -> None:
        if not calls:
            return
        self._ensure_ready()
        now = self.clock()
        with db.transaction(self.path) as connection:
            connection.executemany(
                "INSERT INTO model_calls (session_id, task_id, checkpoint, size, provider, model, step, ok, error,"
                " prompt_tokens, completion_tokens, latency_ms, tools, shown, created_at, purpose)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(session_id, task_id, checkpoint, size, provider, model, call.step, int(call.ok), call.error,
                  call.prompt_tokens, call.completion_tokens, call.latency_ms, json.dumps(call.tools),
                  int(shown), now, purpose) for call in calls])


    def record_routing(self, session_id: str, task_id: str, context: dict, router: str, result, error: str | None,
                       applied: bool) -> None:
        with db.transaction(self.path) as connection:
            connection.execute(
                "INSERT INTO routing_decisions (session_id, task_id, checkpoint, condition, scenario_id, plan, prompt,"
                " router, score, threshold, recommended, ok, error, applied, latency_ms, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, task_id, context["checkpoint"], context["condition"], context["scenarioId"],
                 json.dumps(context["plan"]), context["prompt"], router,
                 result.score if result else None, result.threshold if result else None,
                 result.model if result else None, int(error is None), error, int(applied),
                 result.latency_ms if result else 0, self.clock()))


def load(connection: sqlite3.Connection, session_id: str) -> dict:
    row = connection.execute("SELECT state FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        raise ApiError(404, "SESSION_NOT_FOUND", "Session not found.")
    return json.loads(row["state"])


def save(connection: sqlite3.Connection, session_id: str, state: dict, now: int) -> None:
    connection.execute("UPDATE sessions SET state = ?, updated_at = ? WHERE id = ?",
                       (json.dumps(state), now, session_id))
