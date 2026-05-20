from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Query

from api.schemas import (
    CategoryDeltaV2,
    CompareByIdResponse,
    CostBreakdownItem,
    DegradationPoint,
    HeatmapCellV2,
    ModelSummaryItem,
    RunListItemV2,
    RunSummaryFullResponse,
)
from core.storage import ResultStorage
from evaluators.aggregator import compute_regression_delta

router = APIRouter(prefix="/api/runs", tags=["analytics"])

# Absolute path anchored to the project root so the correct database is found
# regardless of the working directory uvicorn is started from.
_DEFAULT_DB = str(Path(__file__).parent.parent.parent / "data" / "results.duckdb")


def _storage(db_path: str) -> ResultStorage:
    return ResultStorage(db_path)


# ── 1. GET /api/runs ───────────────────────────────────────────────────────────

@router.get("", response_model=List[RunListItemV2])
def list_runs(db_path: str = Query(default=_DEFAULT_DB)):
    """All runs with enriched stats: model_count, test_count, overall_score."""
    rows = _storage(db_path).get_runs_with_stats()
    return [
        RunListItemV2(
            run_id=r["run_id"],
            suite_name=r["suite_name"],
            timestamp=r["created_at"],
            model_count=int(r["model_count"]),
            test_count=int(r["test_count"]),
            overall_score=float(r["overall_score"]) if r["overall_score"] is not None else None,
        )
        for r in rows
    ]


# NOTE: /compare must be declared before /{run_id}/... to avoid path ambiguity.

# ── 5. GET /api/runs/compare?baseline=&candidate= ─────────────────────────────

@router.get("/compare", response_model=List[CompareByIdResponse])
def compare_by_id(
    baseline: str = Query(..., description="Baseline run_id (UUID)"),
    candidate: str = Query(..., description="Candidate run_id (UUID)"),
    db_path: str = Query(default=_DEFAULT_DB),
):
    """Compare two stored runs by ID — no re-run. Returns per-category delta with status."""
    storage = _storage(db_path)

    baseline_list = storage.get_summaries_for_run(baseline)
    candidate_list = storage.get_summaries_for_run(candidate)

    if not baseline_list:
        raise HTTPException(status_code=404, detail=f"Baseline run not found: {baseline}")
    if not candidate_list:
        raise HTTPException(status_code=404, detail=f"Candidate run not found: {candidate}")

    baseline_map = {s.model: s for s in baseline_list}
    candidate_map = {s.model: s for s in candidate_list}

    common = sorted(set(baseline_map) & set(candidate_map))
    if not common:
        raise HTTPException(status_code=422, detail="No common models between the two runs")

    out: List[CompareByIdResponse] = []
    for model in common:
        b = baseline_map[model]
        c = candidate_map[model]
        deltas = compute_regression_delta(b, c)

        all_cats = sorted(set(b.failure_by_category) | set(c.failure_by_category))
        cat_deltas = []
        for cat in all_cats:
            delta = deltas.get(cat, 0.0)
            status = "REGRESSION" if delta > 0.01 else ("IMPROVED" if delta < -0.01 else "OK")
            cat_deltas.append(CategoryDeltaV2(
                category=cat,
                baseline_rate=b.failure_by_category.get(cat, 0.0),
                candidate_rate=c.failure_by_category.get(cat, 0.0),
                delta=delta,
                status=status,
            ))

        overall_delta = c.failure_rate - b.failure_rate
        overall_status = (
            "REGRESSION" if overall_delta > 0.01
            else ("IMPROVED" if overall_delta < -0.01 else "OK")
        )

        out.append(CompareByIdResponse(
            model=model,
            baseline_run_id=baseline,
            candidate_run_id=candidate,
            baseline_failure_rate=b.failure_rate,
            candidate_failure_rate=c.failure_rate,
            overall_delta=overall_delta,
            overall_status=overall_status,
            category_deltas=cat_deltas,
        ))

    return out


# ── 2. GET /api/runs/{run_id}/heatmap ─────────────────────────────────────────

@router.get("/{run_id}/heatmap", response_model=List[HeatmapCellV2])
def get_heatmap(run_id: str, db_path: str = Query(default=_DEFAULT_DB)):
    """Per-category heatmap enriched with disputed flag, depth_level, example_reason."""
    rows = _storage(db_path).get_enriched_heatmap(run_id)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No results found for run {run_id}")
    return [
        HeatmapCellV2(
            model=r["model"],
            category=r["category"],
            depth_level=r["depth_level"],
            failure_rate=float(r["failure_rate"]),
            score=float(r["score"]),
            test_count=int(r["test_count"]),
            example_reason=r["example_reason"],
            disputed=bool(r["disputed"]),
        )
        for r in rows
    ]


# ── 3. GET /api/runs/{run_id}/degradation ─────────────────────────────────────

@router.get("/{run_id}/degradation", response_model=List[DegradationPoint])
def get_degradation(run_id: str, db_path: str = Query(default=_DEFAULT_DB)):
    """Degradation curve: avg score at each context depth level per model + category."""
    rows = _storage(db_path).get_degradation_curve(run_id)
    # Empty list is valid — no depth runs were configured for this suite
    return [
        DegradationPoint(
            model=r["model"],
            failure_category=r["failure_category"],
            depth_level=float(r["depth_level"]),
            avg_score=float(r["avg_score"]),
        )
        for r in rows
    ]


# ── 4. GET /api/runs/{run_id}/summary ─────────────────────────────────────────

@router.get("/{run_id}/summary", response_model=RunSummaryFullResponse)
def get_summary(run_id: str, db_path: str = Query(default=_DEFAULT_DB)):
    """Full run summary: per-model stats, cost breakdown, strongest/weakest model."""
    storage = _storage(db_path)
    summaries = storage.get_summaries_for_run(run_id)
    if not summaries:
        raise HTTPException(status_code=404, detail=f"No data found for run {run_id}")

    cost_rows = storage.get_model_cost_summaries(run_id)

    # Strongest = lowest failure rate; weakest = highest
    ranked = sorted(summaries, key=lambda s: s.failure_rate)
    strongest = ranked[0].model
    weakest = ranked[-1].model

    # Average failure rate per category across all models
    cat_totals: dict[str, list[float]] = {}
    for s in summaries:
        for cat, rate in s.failure_by_category.items():
            cat_totals.setdefault(cat, []).append(rate)
    failure_category_breakdown = {
        cat: sum(rates) / len(rates)
        for cat, rates in cat_totals.items()
    }

    return RunSummaryFullResponse(
        run_id=run_id,
        suite_name=summaries[0].suite_name,
        models=[
            ModelSummaryItem(
                model=s.model,
                total_tests=s.total_tests,
                failed_tests=s.failed_tests,
                failure_rate=s.failure_rate,
                avg_latency_ms=s.avg_latency_ms,
                total_cost_usd=s.total_cost_usd,
                disputed_count=s.disputed_count,
                failure_by_category=s.failure_by_category,
            )
            for s in summaries
        ],
        cost_breakdown=[
            CostBreakdownItem(
                model=r["model"],
                failure_category=r["failure_category"],
                failure_rate=float(r["failure_rate"]),
                avg_score=float(r["avg_score"]),
                estimated_cost_usd=float(r["estimated_cost_usd"]),
                test_count=int(r["test_count"]),
            )
            for r in cost_rows
        ],
        strongest_model=strongest,
        weakest_model=weakest,
        failure_category_breakdown=failure_category_breakdown,
    )
