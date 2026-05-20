from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.schemas import CompareRequest, CompareResponse, CategoryDelta, RunRequest, RunSummaryResponse
from core.config import load_suite
from core.runner import TestRunner
from core.storage import ResultStorage
from evaluators.aggregator import compute_regression_delta

router = APIRouter(prefix="/runs", tags=["runs"])

_DEFAULT_DB = str(Path(__file__).parent.parent.parent / "data" / "results.duckdb")


@router.post("/", response_model=dict)
async def start_run(req: RunRequest, background_tasks: BackgroundTasks):
    """Start a benchmark run. Returns run_id immediately; results stream into DuckDB."""
    run_id = str(uuid.uuid4())

    # Write YAML to temp file so load_suite can parse it
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        f.write(req.suite_yaml)
        tmp_path = f.name

    try:
        config = load_suite(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid suite YAML: {e}")

    if req.db_path:
        config.db_path = req.db_path
    else:
        config.db_path = _DEFAULT_DB

    if req.model_overrides:
        config.models = req.model_overrides

    storage = ResultStorage(config.db_path)
    runner = TestRunner(config, storage)

    # Run in background so the HTTP response returns immediately
    background_tasks.add_task(_run_async, runner, run_id)

    return {"run_id": run_id, "suite_name": config.suite_name, "status": "started"}


async def _run_async(runner: TestRunner, run_id: str):
    await runner.run_suite(run_id)


@router.post("/compare", response_model=list[CompareResponse])
async def compare_runs(req: CompareRequest):
    """Run both suites synchronously and return regression deltas."""
    db_path = req.db_path or _DEFAULT_DB
    storage = ResultStorage(db_path)

    summaries_by_suite = []
    for yaml_content in [req.baseline_yaml, req.candidate_yaml]:
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            config = load_suite(tmp_path)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid suite YAML: {e}")

        config.db_path = db_path
        runner = TestRunner(config, storage)
        summaries = await runner.run_suite()
        summaries_by_suite.append(summaries)

    baseline_summaries, candidate_summaries = summaries_by_suite
    common_models = set(baseline_summaries) & set(candidate_summaries)

    responses = []
    for model in sorted(common_models):
        base = baseline_summaries[model]
        cand = candidate_summaries[model]
        deltas = compute_regression_delta(base, cand)

        all_cats = set(base.failure_by_category) | set(cand.failure_by_category)
        cat_deltas = [
            CategoryDelta(
                category=cat,
                baseline_rate=base.failure_by_category.get(cat, 0.0),
                candidate_rate=cand.failure_by_category.get(cat, 0.0),
                delta=deltas.get(cat, 0.0),
            )
            for cat in sorted(all_cats)
        ]

        responses.append(CompareResponse(
            model=model,
            baseline_run_id=base.run_id,
            candidate_run_id=cand.run_id,
            baseline_failure_rate=base.failure_rate,
            candidate_failure_rate=cand.failure_rate,
            overall_delta=cand.failure_rate - base.failure_rate,
            category_deltas=cat_deltas,
        ))

    return responses
