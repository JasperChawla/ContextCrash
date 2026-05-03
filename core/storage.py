from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Optional

import duckdb

from core.models import DepthScore, ModelCostSummary, RunSummary, TestResult

# Canonical column sets — any deviation from these means the on-disk schema is stale.
# CREATE TABLE IF NOT EXISTS never alters an existing table, so we must detect and
# drop stale tables before recreating them.
_EXPECTED_TEST_RESULT_COLS = frozenset({
    "id", "run_id", "test_case_id", "test_name", "failure_category",
    "perturbation_type", "model", "response", "deterministic_score",
    "llm_judge_score", "final_score", "failed", "failure_reason",
    "judge_rule_disagreement", "disputed", "deterministic_reason",
    "judge_reason", "latency_ms", "prompt_tokens", "completion_tokens",
    "tokens_used", "estimated_cost_usd", "timestamp",
})
_EXPECTED_RUN_SUMMARY_COLS = frozenset({
    "run_id", "suite_name", "model", "total_tests", "failed_tests",
    "failure_rate", "failure_by_category", "avg_latency_ms",
    "judge_disagreement_rate", "disputed_count", "total_cost_usd", "created_at",
})


class ResultStorage:
    """DuckDB-backed storage for all ContextCrash run data.

    Embedded, no server required. WAL mode is set automatically by DuckDB.
    Using fetchall() everywhere to avoid the optional pandas dependency.
    """

    def __init__(self, db_path: str = "./data/results.duckdb"):
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.db_path = db_path
        self._init_schema()

    def _conn(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(self.db_path)

    @staticmethod
    def _to_dicts(cursor) -> List[dict]:
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def _migrate_stale_schema(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Drop any table whose column set no longer matches the expected schema.

        CREATE TABLE IF NOT EXISTS never alters an existing table, so a DB created with an
        older schema will silently keep the wrong columns, causing BinderExceptions at
        INSERT time. Detect stale tables and drop them so the subsequent CREATE TABLE
        rebuilds them correctly. Existing run data is lost, but ContextCrash local dev
        databases are not treated as durable storage.
        """
        tables = {r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()}

        stale_checks = {
            "test_results": _EXPECTED_TEST_RESULT_COLS,
            "run_summaries": _EXPECTED_RUN_SUMMARY_COLS,
        }
        for table, expected in stale_checks.items():
            if table not in tables:
                continue
            existing = {r[0] for r in conn.execute(
                f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}'"
            ).fetchall()}
            if existing != expected:
                print(
                    f"[storage] Stale {table} schema detected "
                    f"({len(existing)} cols, expected {len(expected)}). "
                    "Dropping and recreating — existing rows are lost.",
                    file=sys.stderr,
                )
                conn.execute(f"DROP TABLE {table}")

    def _init_schema(self) -> None:
        with self._conn() as conn:
            self._migrate_stale_schema(conn)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_runs (
                    run_id     VARCHAR PRIMARY KEY,
                    suite_name VARCHAR NOT NULL,
                    models_json VARCHAR NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_results (
                    id                    VARCHAR PRIMARY KEY,
                    run_id                VARCHAR NOT NULL,
                    test_case_id          VARCHAR NOT NULL,
                    test_name             VARCHAR NOT NULL,
                    failure_category      VARCHAR NOT NULL,
                    perturbation_type     VARCHAR NOT NULL,
                    model                 VARCHAR NOT NULL,
                    response              TEXT,
                    deterministic_score   DOUBLE,
                    llm_judge_score       DOUBLE,
                    final_score           DOUBLE NOT NULL,
                    failed                BOOLEAN NOT NULL,
                    failure_reason        VARCHAR,
                    judge_rule_disagreement BOOLEAN DEFAULT FALSE,
                    disputed              BOOLEAN DEFAULT FALSE,
                    deterministic_reason  VARCHAR,
                    judge_reason          VARCHAR,
                    latency_ms            DOUBLE,
                    prompt_tokens         INTEGER DEFAULT 0,
                    completion_tokens     INTEGER DEFAULT 0,
                    tokens_used           INTEGER DEFAULT 0,
                    estimated_cost_usd    DOUBLE DEFAULT 0.0,
                    timestamp             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS run_summaries (
                    run_id                  VARCHAR NOT NULL,
                    suite_name              VARCHAR NOT NULL,
                    model                   VARCHAR NOT NULL,
                    total_tests             INTEGER,
                    failed_tests            INTEGER,
                    failure_rate            DOUBLE,
                    failure_by_category     VARCHAR,
                    avg_latency_ms          DOUBLE,
                    judge_disagreement_rate DOUBLE,
                    disputed_count          INTEGER DEFAULT 0,
                    total_cost_usd          DOUBLE DEFAULT 0.0,
                    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (run_id, model)
                )
            """)
            # ITEM 3 — per-model, per-category cost breakdown
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_cost_summaries (
                    run_id             VARCHAR NOT NULL,
                    model              VARCHAR NOT NULL,
                    failure_category   VARCHAR NOT NULL,
                    failure_rate       DOUBLE,
                    avg_score          DOUBLE,
                    estimated_cost_usd DOUBLE,
                    test_count         INTEGER,
                    PRIMARY KEY (run_id, model, failure_category)
                )
            """)
            # ITEM 4 — degradation curve data points
            conn.execute("""
                CREATE TABLE IF NOT EXISTS depth_scores (
                    run_id           VARCHAR NOT NULL,
                    test_case_id     VARCHAR NOT NULL,
                    model            VARCHAR NOT NULL,
                    depth_level      DOUBLE NOT NULL,
                    score            DOUBLE NOT NULL,
                    failure_category VARCHAR NOT NULL,
                    failed           BOOLEAN NOT NULL,
                    PRIMARY KEY (run_id, test_case_id, model, depth_level)
                )
            """)

    # ── write ops ─────────────────────────────────────────────────────────────

    def create_run(self, run_id: str, suite_name: str, models: list) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO test_runs (run_id, suite_name, models_json, created_at)"
                " VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                [run_id, suite_name, json.dumps(models)],
            )

    async def save_result(self, result: TestResult) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO test_results (
                    id, run_id, test_case_id, test_name,
                    failure_category, perturbation_type, model,
                    response, deterministic_score, llm_judge_score,
                    final_score, failed, failure_reason,
                    judge_rule_disagreement, disputed,
                    deterministic_reason, judge_reason,
                    latency_ms, prompt_tokens, completion_tokens,
                    tokens_used, estimated_cost_usd, timestamp
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    result.id, result.run_id, result.test_case_id, result.test_name,
                    result.failure_category, result.perturbation_type, result.model,
                    result.response, result.deterministic_score, result.llm_judge_score,
                    result.final_score, result.failed, result.failure_reason,
                    result.judge_rule_disagreement, result.disputed,
                    result.deterministic_reason, result.judge_reason,
                    result.latency_ms, result.prompt_tokens, result.completion_tokens,
                    result.tokens_used, result.estimated_cost_usd, result.timestamp,
                ],
            )

    def save_summary(self, summary: RunSummary) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO run_summaries (
                    run_id, suite_name, model,
                    total_tests, failed_tests, failure_rate,
                    failure_by_category, avg_latency_ms,
                    judge_disagreement_rate, disputed_count,
                    total_cost_usd, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                [
                    summary.run_id, summary.suite_name, summary.model,
                    summary.total_tests, summary.failed_tests, summary.failure_rate,
                    json.dumps(summary.failure_by_category), summary.avg_latency_ms,
                    summary.judge_disagreement_rate, summary.disputed_count,
                    summary.total_cost_usd,
                ],
            )

    def save_model_cost_summary(self, s: ModelCostSummary) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO model_cost_summaries (
                    run_id, model, failure_category,
                    failure_rate, avg_score, estimated_cost_usd, test_count
                ) VALUES (?,?,?,?,?,?,?)""",
                [s.run_id, s.model, s.failure_category,
                 s.failure_rate, s.avg_score, s.estimated_cost_usd, s.test_count],
            )

    async def save_depth_score(self, ds: DepthScore) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO depth_scores (
                    run_id, test_case_id, model, depth_level,
                    score, failure_category, failed
                ) VALUES (?,?,?,?,?,?,?)""",
                [ds.run_id, ds.test_case_id, ds.model, ds.depth_level,
                 ds.score, ds.failure_category, ds.failed],
            )

    # ── read ops ──────────────────────────────────────────────────────────────

    def get_results_for_run(self, run_id: str) -> List[dict]:
        with self._conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM test_results WHERE run_id = ?", [run_id]
            )
            return self._to_dicts(cursor)

    def get_summaries_for_run(self, run_id: str) -> List[RunSummary]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM run_summaries WHERE run_id = ?", [run_id]
            ).fetchall()
            return [
                RunSummary(
                    run_id=row[0], suite_name=row[1], model=row[2],
                    total_tests=row[3], failed_tests=row[4], failure_rate=row[5],
                    failure_by_category=json.loads(row[6]), avg_latency_ms=row[7],
                    judge_disagreement_rate=row[8],
                    disputed_count=row[9] if len(row) > 9 else 0,
                    total_cost_usd=row[10] if len(row) > 10 else 0.0,
                    timestamp=row[11] if len(row) > 11 else None,
                )
                for row in rows
            ]

    def get_all_runs(self) -> List[dict]:
        with self._conn() as conn:
            cursor = conn.execute("SELECT * FROM test_runs ORDER BY created_at DESC")
            return self._to_dicts(cursor)

    def get_latest_run_for_suite(self, suite_name: str) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT run_id FROM test_runs WHERE suite_name = ?"
                " ORDER BY created_at DESC LIMIT 1",
                [suite_name],
            ).fetchone()
            return row[0] if row else None

    def get_failure_heatmap(self, run_id: str) -> List[dict]:
        with self._conn() as conn:
            cursor = conn.execute(
                """
                SELECT model, failure_category,
                       COUNT(*) AS total,
                       SUM(CASE WHEN failed THEN 1 ELSE 0 END) AS failures,
                       AVG(final_score) AS avg_score
                FROM test_results
                WHERE run_id = ?
                GROUP BY model, failure_category
                ORDER BY model, failure_category
                """,
                [run_id],
            )
            return self._to_dicts(cursor)

    def get_model_cost_summaries(self, run_id: str) -> List[dict]:
        with self._conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM model_cost_summaries WHERE run_id = ? ORDER BY model, failure_category",
                [run_id],
            )
            return self._to_dicts(cursor)

    def get_degradation_data(self, run_id: str) -> List[dict]:
        """Returns depth-score rows for plotting degradation curves."""
        with self._conn() as conn:
            cursor = conn.execute(
                """SELECT * FROM depth_scores WHERE run_id = ?
                   ORDER BY model, failure_category, depth_level""",
                [run_id],
            )
            return self._to_dicts(cursor)

    # ── Phase 3A read ops ─────────────────────────────────────────────────────

    def get_runs_with_stats(self) -> List[dict]:
        """Runs list enriched with model_count, test_count, overall_score."""
        with self._conn() as conn:
            cursor = conn.execute("""
                SELECT
                    r.run_id,
                    r.suite_name,
                    r.created_at,
                    COUNT(DISTINCT s.model)                  AS model_count,
                    COALESCE(MAX(s.total_tests), 0)          AS test_count,
                    CASE WHEN COUNT(s.model) > 0
                         THEN 1.0 - AVG(s.failure_rate)
                         ELSE NULL
                    END                                      AS overall_score
                FROM test_runs r
                LEFT JOIN run_summaries s USING (run_id)
                GROUP BY r.run_id, r.suite_name, r.created_at
                ORDER BY r.created_at DESC
            """)
            return self._to_dicts(cursor)

    def get_enriched_heatmap(self, run_id: str) -> List[dict]:
        """Per-(model, category) heatmap with example_reason, disputed, depth_level."""
        with self._conn() as conn:
            cursor = conn.execute("""
                SELECT
                    model,
                    failure_category                                     AS category,
                    COUNT(*)                                             AS test_count,
                    AVG(CASE WHEN failed THEN 1.0 ELSE 0.0 END)         AS failure_rate,
                    AVG(final_score)                                     AS score,
                    MAX(CAST(disputed AS INTEGER))                       AS any_disputed,
                    MIN(failure_reason)                                  AS example_reason
                FROM test_results
                WHERE run_id = ?
                GROUP BY model, failure_category
                ORDER BY model, failure_category
            """, [run_id])
            rows = self._to_dicts(cursor)

            # Shallowest depth at which a failure was observed, per (model, category)
            depth_rows = conn.execute("""
                SELECT model, failure_category, MIN(depth_level) AS depth_level
                FROM depth_scores
                WHERE run_id = ? AND failed = TRUE
                GROUP BY model, failure_category
            """, [run_id]).fetchall()
            depth_map = {(r[0], r[1]): r[2] for r in depth_rows}

        for row in rows:
            row["depth_level"] = depth_map.get((row["model"], row["category"]))
            row["disputed"] = bool(row.pop("any_disputed"))
        return rows

    def get_degradation_curve(self, run_id: str) -> List[dict]:
        """Avg score per (model, category, depth_level) for degradation curve plots."""
        with self._conn() as conn:
            cursor = conn.execute("""
                SELECT model, failure_category, depth_level, AVG(score) AS avg_score
                FROM depth_scores
                WHERE run_id = ?
                GROUP BY model, failure_category, depth_level
                ORDER BY model, failure_category, depth_level
            """, [run_id])
            return self._to_dicts(cursor)

    # ── cleanup ops ───────────────────────────────────────────────────────────

    def delete_stale_runs(self) -> int:
        """Delete runs that have no summaries (model_count=0 / test_count=0).

        These are typically runs created before a schema fix where results were
        lost, or runs that failed before any data was written.
        Returns the number of run records deleted.
        """
        _RESULT_TABLES = [
            "test_results", "run_summaries",
            "model_cost_summaries", "depth_scores",
        ]
        with self._conn() as conn:
            stale = [r[0] for r in conn.execute("""
                SELECT r.run_id
                FROM test_runs r
                LEFT JOIN run_summaries s USING (run_id)
                WHERE s.run_id IS NULL
            """).fetchall()]

            if not stale:
                return 0

            for table in _RESULT_TABLES:
                for run_id in stale:
                    conn.execute(f"DELETE FROM {table} WHERE run_id = ?", [run_id])
            for run_id in stale:
                conn.execute("DELETE FROM test_runs WHERE run_id = ?", [run_id])

            return len(stale)

    def delete_all_runs(self) -> int:
        """Delete every row from all run-data tables. Returns number of runs deleted."""
        _ALL_TABLES = [
            "test_results", "run_summaries",
            "model_cost_summaries", "depth_scores", "test_runs",
        ]
        with self._conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM test_runs").fetchone()[0]
            for table in _ALL_TABLES:
                conn.execute(f"DELETE FROM {table}")
            return count

    def get_schema(self) -> List[dict]:
        """Returns all table names and their columns — used for the final check."""
        with self._conn() as conn:
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
            result = []
            for (tbl,) in tables:
                cols = conn.execute(
                    f"SELECT column_name, data_type FROM information_schema.columns"
                    f" WHERE table_name='{tbl}' ORDER BY ordinal_position"
                ).fetchall()
                result.append({"table": tbl, "columns": [{"name": c, "type": t} for c, t in cols]})
            return result
