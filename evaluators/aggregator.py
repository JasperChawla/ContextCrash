from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from core.models import RunSummary, TestResult


def build_summary(
    run_id: str,
    suite_name: str,
    model: str,
    results: List[TestResult],
) -> RunSummary:
    if not results:
        return RunSummary(
            run_id=run_id,
            suite_name=suite_name,
            model=model,
            total_tests=0,
            failed_tests=0,
            failure_rate=0.0,
            failure_by_category={},
            avg_latency_ms=0.0,
            judge_disagreement_rate=0.0,
            disputed_count=0,
            total_cost_usd=0.0,
        )

    by_category: Dict[str, List[TestResult]] = defaultdict(list)
    for r in results:
        by_category[r.failure_category].append(r)

    failure_by_category = {
        cat: sum(1 for r in rs if r.failed) / len(rs)
        for cat, rs in by_category.items()
    }

    total = len(results)
    failed = sum(1 for r in results if r.failed)
    # ITEM 2: count both old field and new disputed field for backward compat
    disagreements = sum(1 for r in results if r.disputed or r.judge_rule_disagreement)
    disputed = sum(1 for r in results if r.disputed)
    # ITEM 3: total estimated cost for this model's run
    total_cost = sum(r.estimated_cost_usd for r in results)

    return RunSummary(
        run_id=run_id,
        suite_name=suite_name,
        model=model,
        total_tests=total,
        failed_tests=failed,
        failure_rate=failed / total,
        failure_by_category=failure_by_category,
        avg_latency_ms=sum(r.latency_ms for r in results) / total,
        judge_disagreement_rate=disagreements / total,
        disputed_count=disputed,
        total_cost_usd=total_cost,
    )


def compute_regression_delta(
    baseline: RunSummary,
    candidate: RunSummary,
) -> Dict[str, float]:
    """Returns per-category delta. Positive = regression (higher failure rate)."""
    all_cats = set(baseline.failure_by_category) | set(candidate.failure_by_category)
    return {
        cat: candidate.failure_by_category.get(cat, 0.0)
             - baseline.failure_by_category.get(cat, 0.0)
        for cat in all_cats
    }
