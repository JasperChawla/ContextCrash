from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Query

from api.schemas import HeatmapCell, RunListItem, RunSummaryResponse
from core.storage import ResultStorage

router = APIRouter(prefix="/results", tags=["results"])

_DEFAULT_DB = str(Path(__file__).parent.parent.parent / "data" / "results.duckdb")


def _get_storage(db_path: str = _DEFAULT_DB) -> ResultStorage:
    return ResultStorage(db_path)


@router.get("/runs", response_model=List[dict])
def list_runs(db_path: str = Query(default=_DEFAULT_DB)):
    storage = _get_storage(db_path)
    return storage.get_all_runs()


@router.get("/runs/{run_id}/summaries", response_model=List[RunSummaryResponse])
def get_summaries(run_id: str, db_path: str = Query(default=_DEFAULT_DB)):
    storage = _get_storage(db_path)
    summaries = storage.get_summaries_for_run(run_id)
    if not summaries:
        raise HTTPException(status_code=404, detail=f"No summaries found for run {run_id}")
    return [
        RunSummaryResponse(
            run_id=s.run_id,
            suite_name=s.suite_name,
            model=s.model,
            total_tests=s.total_tests,
            failed_tests=s.failed_tests,
            failure_rate=s.failure_rate,
            failure_by_category=s.failure_by_category,
            avg_latency_ms=s.avg_latency_ms,
            judge_disagreement_rate=s.judge_disagreement_rate,
            timestamp=s.timestamp,
        )
        for s in summaries
    ]


@router.get("/runs/{run_id}/heatmap", response_model=List[HeatmapCell])
def get_heatmap(run_id: str, db_path: str = Query(default=_DEFAULT_DB)):
    storage = _get_storage(db_path)
    rows = storage.get_failure_heatmap(run_id)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No results found for run {run_id}")
    return [
        HeatmapCell(
            model=r["model"],
            category=r["failure_category"],
            failure_rate=r["failures"] / r["total"] if r["total"] > 0 else 0.0,
            total=int(r["total"]),
            avg_score=float(r["avg_score"]),
        )
        for r in rows
    ]


@router.get("/runs/{run_id}/raw", response_model=List[dict])
def get_raw_results(run_id: str, db_path: str = Query(default=_DEFAULT_DB)):
    storage = _get_storage(db_path)
    results = storage.get_results_for_run(run_id)
    if not results:
        raise HTTPException(status_code=404, detail=f"No results found for run {run_id}")
    return results
