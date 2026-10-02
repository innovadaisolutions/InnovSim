"""SQLite persistence with immutable run snapshots and editable scenario drafts."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from threading import RLock

from .fixtures import default_scenarios
from .models import Run, Scenario
from .refinement import apply_refinement
from .simulation import AgentAdapter, simulate


class NotFoundError(LookupError):
    pass


class Repository:
    def __init__(self, database_path: str | Path | None = None) -> None:
        self.path = str(database_path or os.environ.get("AW_DATABASE_PATH", "data/workbench.db"))
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
            self.path = str(Path(self.path).expanduser())
        self._lock = RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS scenarios (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                scenario_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                parent_run_id TEXT REFERENCES runs(id),
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS runs_created_at ON runs(created_at DESC);
            CREATE TRIGGER IF NOT EXISTS runs_immutable_update
            BEFORE UPDATE ON runs BEGIN SELECT RAISE(ABORT, 'Run snapshots are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS runs_immutable_delete
            BEFORE DELETE ON runs BEGIN SELECT RAISE(ABORT, 'Run snapshots are immutable'); END;
        """)
        with self._connection:
            for scenario in default_scenarios():
                self._connection.execute(
                    "INSERT OR IGNORE INTO scenarios(id, payload) VALUES (?, ?)",
                    (scenario.id, scenario.model_dump_json()),
                )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def list_scenarios(self) -> list[Scenario]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT payload FROM scenarios ORDER BY rowid"
            ).fetchall()
        return [Scenario.model_validate_json(row[0]) for row in rows]

    def get_scenario(self, scenario_id: str) -> Scenario:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload FROM scenarios WHERE id = ?", (scenario_id,)
            ).fetchone()
        if not row:
            raise NotFoundError(f"Scenario {scenario_id!r} was not found.")
        return Scenario.model_validate_json(row[0])

    def save_scenario(self, scenario: Scenario) -> Scenario:
        validated = Scenario.model_validate(scenario.model_dump())
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO scenarios(id, payload) VALUES (?, ?) "
                "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                (validated.id, validated.model_dump_json()),
            )
        return validated

    def list_runs(self) -> list[Run]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT payload FROM runs ORDER BY created_at DESC, rowid DESC LIMIT 50"
            ).fetchall()
        return [Run.model_validate_json(row[0]) for row in rows]

    def get_run(self, run_id: str) -> Run:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
        if not row:
            raise NotFoundError(f"Run {run_id!r} was not found.")
        return Run.model_validate_json(row[0])

    def save_run(self, run: Run) -> Run:
        validated = Run.model_validate(run.model_dump())
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO runs(id, scenario_id, created_at, parent_run_id, payload) VALUES (?, ?, ?, ?, ?)",
                (
                    validated.id,
                    validated.scenario_id,
                    validated.created_at,
                    validated.parent_run_id,
                    validated.model_dump_json(),
                ),
            )
        return validated

    def run_scenario(self, scenario_id: str) -> Run:
        return self.save_run(simulate(self.get_scenario(scenario_id)))

    def refine_run(
        self, run_id: str, suggestion_id: str, *, adapter: AgentAdapter | None = None
    ) -> Run:
        parent = self.get_run(run_id)
        adapter_name = adapter.name if adapter is not None else "deterministic"
        if parent.adapter != adapter_name:
            raise ValueError(
                "Refinement must use the same adapter as the parent run. "
                "Pass the trusted Python adapter explicitly when refining custom runs locally."
            )
        suggestion = next((item for item in parent.suggestions if item.id == suggestion_id), None)
        if suggestion is None:
            raise NotFoundError(f"Suggestion {suggestion_id!r} was not found in this run.")
        candidate = apply_refinement(parent.configuration, suggestion.patch)
        # Use the immutable parent configuration, rather than an edited scenario draft.
        return self.save_run(simulate(candidate, adapter=adapter, parent_run_id=parent.id))
