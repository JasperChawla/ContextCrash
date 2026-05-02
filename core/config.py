from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from core.models import (
    FailureCategory,
    PerturbationType,
    RunConfig,
    TestCase,
    ValidatorSpec,
)
from perturbations import get_perturbation
from perturbations.history_contamination import HistoryContaminationPerturbation


def load_suite(path: str) -> RunConfig:
    """Parse a suite YAML file into a RunConfig with perturbations already applied."""
    suite_path = Path(path)
    with suite_path.open() as f:
        raw = yaml.safe_load(f)

    defaults = raw.get("defaults", {})
    default_system_prompt = defaults.get("system_prompt", "")
    default_max_tokens = defaults.get("max_tokens", 1024)

    test_cases = []
    for tc_raw in raw.get("test_cases", []):
        test_cases.append(_load_test_case(tc_raw, default_system_prompt))

    # ITEM 6 — optional retrieval pipeline knobs section
    r = raw.get("retrieval", {})

    return RunConfig(
        suite_name=raw["suite"]["name"],
        models=raw.get("models", ["gpt-4o"]),
        test_cases=test_cases,
        judge_model=raw.get("judge_model", "claude-opus-4-5"),
        parallel_workers=raw.get("parallel_workers", 5),
        db_path=raw.get("db_path", "./data/results.duckdb"),
        failure_threshold=raw.get("failure_threshold", 0.5),
        chunk_size=r.get("chunk_size", 512),
        chunk_overlap=r.get("chunk_overlap", 50),
        top_k=r.get("top_k", 5),
        reranking_enabled=r.get("reranking_enabled", False),
        chunk_ordering=r.get("chunk_ordering", "sequential"),
    )


def _load_test_case(raw: Dict[str, Any], default_system_prompt: str) -> TestCase:
    perturbation_type = PerturbationType(raw.get("perturbation", "chunk_shuffle"))
    perturbation_config = raw.get("perturbation_config", {})
    chunks = raw.get("chunks", [])

    # Apply chunk-level perturbation
    perturbation = get_perturbation(perturbation_type)
    perturbed_chunks = perturbation.apply(chunks, perturbation_config)

    # History contamination is special - it modifies conversation history, not chunks
    history = raw.get("history", [])
    if perturbation_type == PerturbationType.HISTORY_CONTAMINATION:
        history = HistoryContaminationPerturbation.get_contaminated_history(
            history, perturbation_config
        )

    # Parse optional custom validators
    validators = [
        ValidatorSpec(**v) for v in raw.get("validators", [])
    ]

    return TestCase(
        name=raw["name"],
        failure_category=FailureCategory(raw["failure_category"]),
        perturbation_type=perturbation_type,
        system_prompt=raw.get("system_prompt", default_system_prompt),
        chunks=perturbed_chunks,
        conversation_history=history,
        user_query=raw["query"],
        expected_behavior=raw["expected_behavior"],
        validators=validators,
        metadata=raw.get("metadata", {}),
        # ITEM 4 — depth levels for degradation curves
        context_depth_levels=raw.get("context_depth_levels", []),
        # ITEM 6 — per-test chunk ordering override
        chunk_ordering=raw.get("chunk_ordering", None),
    )
