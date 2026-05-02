"""
Phase 3A API tests — all 5 analytics endpoints verified with seeded DuckDB data.
Uses FastAPI TestClient (synchronous), no real model calls.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.models import DepthScore, RunSummary, TestResult
from core.storage import ResultStorage

client = TestClient(app)

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_result(run_id: str, model: str, category: str, failed: bool, score: float,
                 disputed: bool = False, reason: str | None = None) -> TestResult:
    return TestResult(
        run_id=run_id,
        test_case_id=f"{category}-{model}",
        test_name=f"test_{category}",
        failure_category=category,
        perturbation_type="chunk_shuffle",
        model=model,
        response="mock response",
        final_score=score,
        failed=failed,
        failure_reason=reason if failed else None,
        disputed=disputed,
        latency_ms=100.0,
    )


def _make_summary(run_id: str, suite: str, model: str, results: list[TestResult]) -> RunSummary:
    total = len(results)
    failed = sum(1 for r in results if r.failed)
    by_cat: dict[str, list[float]] = {}
    for r in results:
        by_cat.setdefault(r.failure_category, []).append(1.0 if r.failed else 0.0)
    return RunSummary(
        run_id=run_id,
        suite_name=suite,
        model=model,
        total_tests=total,
        failed_tests=failed,
        failure_rate=failed / total if total else 0.0,
        failure_by_category={c: sum(v) / len(v) for c, v in by_cat.items()},
        avg_latency_ms=100.0,
        judge_disagreement_rate=0.0,
        disputed_count=sum(1 for r in results if r.disputed),
        total_cost_usd=0.001,
    )


def _seed(tmp_path, run_id: str = "run-aaa", suite: str = "Suite A",
          models: list[str] | None = None) -> tuple[str, str]:
    """Seed one run with two models and return (db_path, run_id)."""
    if models is None:
        models = ["gpt-4o", "claude-haiku"]
    db_path = str(tmp_path / "test.duckdb")
    storage = ResultStorage(db_path)
    storage.create_run(run_id, suite, models)

    all_results: dict[str, list[TestResult]] = {m: [] for m in models}

    for model in models:
        r1 = _make_result(run_id, model, "instruction_loss", failed=True,  score=0.2, reason="No citation")
        r2 = _make_result(run_id, model, "instruction_loss", failed=False, score=0.9)
        r3 = _make_result(run_id, model, "hallucination_overload", failed=False, score=0.8)
        for r in (r1, r2, r3):
            asyncio.run(storage.save_result(r))
            all_results[model].append(r)

        summary = _make_summary(run_id, suite, model, all_results[model])
        storage.save_summary(summary)

        from core.models import ModelCostSummary
        storage.save_model_cost_summary(ModelCostSummary(
            run_id=run_id, model=model, failure_category="instruction_loss",
            failure_rate=0.5, avg_score=0.55, estimated_cost_usd=0.0005, test_count=2,
        ))
        storage.save_model_cost_summary(ModelCostSummary(
            run_id=run_id, model=model, failure_category="hallucination_overload",
            failure_rate=0.0, avg_score=0.8, estimated_cost_usd=0.0002, test_count=1,
        ))

    return db_path, run_id


# ── 1. GET /api/runs ──────────────────────────────────────────────────────────

class TestListRuns:
    def test_returns_200_with_runs(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs?db_path={db_path}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["run_id"] == run_id

    def test_response_contains_required_fields(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs?db_path={db_path}")
        item = resp.json()[0]
        assert "run_id" in item
        assert "suite_name" in item
        assert "timestamp" in item
        assert "model_count" in item
        assert "test_count" in item
        assert "overall_score" in item

    def test_model_count_reflects_seeded_models(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs?db_path={db_path}")
        assert resp.json()[0]["model_count"] == 2

    def test_test_count_reflects_seeded_tests(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs?db_path={db_path}")
        # 3 tests per model
        assert resp.json()[0]["test_count"] == 3

    def test_overall_score_between_0_and_1(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs?db_path={db_path}")
        score = resp.json()[0]["overall_score"]
        assert score is not None
        assert 0.0 <= score <= 1.0

    def test_empty_db_returns_empty_list(self, tmp_path):
        db_path = str(tmp_path / "empty.duckdb")
        ResultStorage(db_path)  # init schema only
        resp = client.get(f"/api/runs?db_path={db_path}")
        assert resp.status_code == 200
        assert resp.json() == []


# ── 2. GET /api/runs/{run_id}/heatmap ────────────────────────────────────────

class TestHeatmap:
    def test_returns_200_with_data(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs/{run_id}/heatmap?db_path={db_path}")
        assert resp.status_code == 200
        assert len(resp.json()) > 0

    def test_response_contains_required_fields(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs/{run_id}/heatmap?db_path={db_path}")
        cell = resp.json()[0]
        assert "model" in cell
        assert "category" in cell
        assert "depth_level" in cell
        assert "failure_rate" in cell
        assert "score" in cell
        assert "test_count" in cell
        assert "example_reason" in cell
        assert "disputed" in cell

    def test_failure_rate_matches_seeded_data(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs/{run_id}/heatmap?db_path={db_path}")
        # instruction_loss: 1 fail out of 2 tests = 0.5
        il_cells = [c for c in resp.json() if c["category"] == "instruction_loss"]
        assert len(il_cells) > 0
        assert il_cells[0]["failure_rate"] == pytest.approx(0.5, abs=0.01)

    def test_example_reason_populated_for_failed_category(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs/{run_id}/heatmap?db_path={db_path}")
        il_cells = [c for c in resp.json() if c["category"] == "instruction_loss"]
        assert il_cells[0]["example_reason"] == "No citation"

    def test_depth_level_null_when_no_depth_runs(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs/{run_id}/heatmap?db_path={db_path}")
        for cell in resp.json():
            assert cell["depth_level"] is None

    def test_disputed_flag_present(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs/{run_id}/heatmap?db_path={db_path}")
        for cell in resp.json():
            assert isinstance(cell["disputed"], bool)

    def test_404_for_unknown_run(self, tmp_path):
        db_path = str(tmp_path / "empty.duckdb")
        ResultStorage(db_path)
        resp = client.get(f"/api/runs/nonexistent/heatmap?db_path={db_path}")
        assert resp.status_code == 404


# ── 3. GET /api/runs/{run_id}/degradation ────────────────────────────────────

class TestDegradation:
    def test_returns_200_empty_list_when_no_depth_data(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs/{run_id}/degradation?db_path={db_path}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_depth_points_when_seeded(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        storage = ResultStorage(db_path)

        for depth in [0.25, 0.5, 1.0]:
            asyncio.run(storage.save_depth_score(DepthScore(
                run_id=run_id,
                test_case_id="tc-depth-1",
                model="gpt-4o",
                depth_level=depth,
                score=0.9 - depth * 0.3,
                failure_category="instruction_loss",
                failed=depth > 0.6,
            )))

        resp = client.get(f"/api/runs/{run_id}/degradation?db_path={db_path}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    def test_response_fields(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        storage = ResultStorage(db_path)
        asyncio.run(storage.save_depth_score(DepthScore(
            run_id=run_id, test_case_id="tc1", model="gpt-4o",
            depth_level=0.5, score=0.7, failure_category="hallucination_overload", failed=False,
        )))

        resp = client.get(f"/api/runs/{run_id}/degradation?db_path={db_path}")
        point = resp.json()[0]
        assert "model" in point
        assert "failure_category" in point
        assert "depth_level" in point
        assert "avg_score" in point

    def test_avg_score_aggregated_across_test_cases(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        storage = ResultStorage(db_path)

        # Two test cases at same depth — avg_score should be average
        for tc_id, score in [("tc-a", 0.8), ("tc-b", 0.4)]:
            asyncio.run(storage.save_depth_score(DepthScore(
                run_id=run_id, test_case_id=tc_id, model="gpt-4o",
                depth_level=0.5, score=score, failure_category="instruction_loss", failed=False,
            )))

        resp = client.get(f"/api/runs/{run_id}/degradation?db_path={db_path}")
        points = [p for p in resp.json() if p["model"] == "gpt-4o" and p["depth_level"] == 0.5]
        assert len(points) == 1
        assert points[0]["avg_score"] == pytest.approx(0.6, abs=0.01)


# ── 4. GET /api/runs/{run_id}/summary ────────────────────────────────────────

class TestSummary:
    def test_returns_200_with_summary(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs/{run_id}/summary?db_path={db_path}")
        assert resp.status_code == 200

    def test_required_fields_present(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs/{run_id}/summary?db_path={db_path}")
        data = resp.json()
        assert data["run_id"] == run_id
        assert "suite_name" in data
        assert "models" in data
        assert "cost_breakdown" in data
        assert "strongest_model" in data
        assert "weakest_model" in data
        assert "failure_category_breakdown" in data

    def test_models_list_contains_both_models(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs/{run_id}/summary?db_path={db_path}")
        model_names = [m["model"] for m in resp.json()["models"]]
        assert "gpt-4o" in model_names
        assert "claude-haiku" in model_names

    def test_cost_breakdown_per_model_category(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs/{run_id}/summary?db_path={db_path}")
        # 2 models × 2 categories = 4 cost rows seeded
        assert len(resp.json()["cost_breakdown"]) == 4

    def test_strongest_weakest_model_are_strings(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs/{run_id}/summary?db_path={db_path}")
        data = resp.json()
        assert isinstance(data["strongest_model"], str)
        assert isinstance(data["weakest_model"], str)

    def test_failure_category_breakdown_keys(self, tmp_path):
        db_path, run_id = _seed(tmp_path)
        resp = client.get(f"/api/runs/{run_id}/summary?db_path={db_path}")
        breakdown = resp.json()["failure_category_breakdown"]
        assert "instruction_loss" in breakdown
        assert "hallucination_overload" in breakdown

    def test_404_for_unknown_run(self, tmp_path):
        db_path = str(tmp_path / "empty.duckdb")
        ResultStorage(db_path)
        resp = client.get(f"/api/runs/no-such-run/summary?db_path={db_path}")
        assert resp.status_code == 404


# ── 5. GET /api/runs/compare?baseline=&candidate= ────────────────────────────

class TestCompareByRunId:
    def _two_runs(self, tmp_path) -> tuple[str, str, str]:
        """Seed two runs with different failure rates and return (db, run_a, run_b)."""
        db_path = str(tmp_path / "compare.duckdb")
        storage = ResultStorage(db_path)

        for run_id, fr in [("run-base", 0.0), ("run-cand", 1.0)]:
            storage.create_run(run_id, "Suite", ["gpt-4o"])
            r = _make_result(run_id, "gpt-4o", "instruction_loss",
                             failed=(fr == 1.0), score=0.2 if fr == 1.0 else 0.9,
                             reason="fail" if fr == 1.0 else None)
            asyncio.run(storage.save_result(r))
            summary = _make_summary(run_id, "Suite", "gpt-4o", [r])
            storage.save_summary(summary)

        return db_path, "run-base", "run-cand"

    def test_returns_200(self, tmp_path):
        db_path, base, cand = self._two_runs(tmp_path)
        resp = client.get(f"/api/runs/compare?baseline={base}&candidate={cand}&db_path={db_path}")
        assert resp.status_code == 200

    def test_response_contains_required_fields(self, tmp_path):
        db_path, base, cand = self._two_runs(tmp_path)
        resp = client.get(f"/api/runs/compare?baseline={base}&candidate={cand}&db_path={db_path}")
        item = resp.json()[0]
        assert "model" in item
        assert "baseline_run_id" in item
        assert "candidate_run_id" in item
        assert "overall_delta" in item
        assert "overall_status" in item
        assert "category_deltas" in item

    def test_regression_detected(self, tmp_path):
        db_path, base, cand = self._two_runs(tmp_path)
        resp = client.get(f"/api/runs/compare?baseline={base}&candidate={cand}&db_path={db_path}")
        data = resp.json()[0]
        assert data["overall_delta"] > 0
        assert data["overall_status"] == "REGRESSION"

    def test_improvement_detected(self, tmp_path):
        # Swap baseline and candidate so candidate is better
        db_path, base, cand = self._two_runs(tmp_path)
        resp = client.get(f"/api/runs/compare?baseline={cand}&candidate={base}&db_path={db_path}")
        data = resp.json()[0]
        assert data["overall_delta"] < 0
        assert data["overall_status"] == "IMPROVED"

    def test_category_delta_status_labels(self, tmp_path):
        db_path, base, cand = self._two_runs(tmp_path)
        resp = client.get(f"/api/runs/compare?baseline={base}&candidate={cand}&db_path={db_path}")
        cat_deltas = resp.json()[0]["category_deltas"]
        statuses = {d["status"] for d in cat_deltas}
        # At least one REGRESSION since cand has higher failure rate
        assert "REGRESSION" in statuses

    def test_404_when_baseline_not_found(self, tmp_path):
        db_path = str(tmp_path / "empty.duckdb")
        ResultStorage(db_path)
        resp = client.get(f"/api/runs/compare?baseline=no-such&candidate=also-no&db_path={db_path}")
        assert resp.status_code == 404

    def test_run_ids_reflected_in_response(self, tmp_path):
        db_path, base, cand = self._two_runs(tmp_path)
        resp = client.get(f"/api/runs/compare?baseline={base}&candidate={cand}&db_path={db_path}")
        data = resp.json()[0]
        assert data["baseline_run_id"] == base
        assert data["candidate_run_id"] == cand

    def test_ok_status_when_no_change(self, tmp_path):
        """Two identical runs → all deltas are 0 → status OK."""
        db_path = str(tmp_path / "ok.duckdb")
        storage = ResultStorage(db_path)

        for run_id in ("run-x", "run-y"):
            storage.create_run(run_id, "Suite", ["gpt-4o"])
            r = _make_result(run_id, "gpt-4o", "instruction_loss", failed=False, score=0.9)
            asyncio.run(storage.save_result(r))
            storage.save_summary(_make_summary(run_id, "Suite", "gpt-4o", [r]))

        resp = client.get(f"/api/runs/compare?baseline=run-x&candidate=run-y&db_path={db_path}")
        assert resp.status_code == 200
        for cat in resp.json()[0]["category_deltas"]:
            assert cat["status"] == "OK"
