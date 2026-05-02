from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class RunRequest(BaseModel):
    suite_yaml: str  # raw YAML content
    db_path: Optional[str] = None
    model_overrides: Optional[List[str]] = None


class HeatmapCell(BaseModel):
    model: str
    category: str
    failure_rate: float
    total: int
    avg_score: float


class RunSummaryResponse(BaseModel):
    run_id: str
    suite_name: str
    model: str
    total_tests: int
    failed_tests: int
    failure_rate: float
    failure_by_category: Dict[str, float]
    avg_latency_ms: float
    judge_disagreement_rate: float
    timestamp: datetime


class RunListItem(BaseModel):
    run_id: str
    suite_name: str
    models: List[str]
    created_at: datetime


class CompareRequest(BaseModel):
    baseline_yaml: str
    candidate_yaml: str
    db_path: Optional[str] = None


class CategoryDelta(BaseModel):
    category: str
    baseline_rate: float
    candidate_rate: float
    delta: float  # positive = regression


class CompareResponse(BaseModel):
    model: str
    baseline_run_id: str
    candidate_run_id: str
    baseline_failure_rate: float
    candidate_failure_rate: float
    overall_delta: float
    category_deltas: List[CategoryDelta]


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# ── Phase 3A schemas ──────────────────────────────────────────────────────────

class RunListItemV2(BaseModel):
    run_id: str
    suite_name: str
    timestamp: datetime
    model_count: int
    test_count: int
    overall_score: Optional[float]


class HeatmapCellV2(BaseModel):
    model: str
    category: str
    depth_level: Optional[float]
    failure_rate: float
    score: float
    test_count: int
    example_reason: Optional[str]
    disputed: bool


class DegradationPoint(BaseModel):
    model: str
    failure_category: str
    depth_level: float
    avg_score: float


class ModelSummaryItem(BaseModel):
    model: str
    total_tests: int
    failed_tests: int
    failure_rate: float
    avg_latency_ms: float
    total_cost_usd: float
    disputed_count: int
    failure_by_category: Dict[str, float]


class CostBreakdownItem(BaseModel):
    model: str
    failure_category: str
    failure_rate: float
    avg_score: float
    estimated_cost_usd: float
    test_count: int


class RunSummaryFullResponse(BaseModel):
    run_id: str
    suite_name: str
    models: List[ModelSummaryItem]
    cost_breakdown: List[CostBreakdownItem]
    strongest_model: Optional[str]
    weakest_model: Optional[str]
    failure_category_breakdown: Dict[str, float]


class CategoryDeltaV2(BaseModel):
    category: str
    baseline_rate: float
    candidate_rate: float
    delta: float
    status: str  # "OK" | "REGRESSION" | "IMPROVED"


class CompareByIdResponse(BaseModel):
    model: str
    baseline_run_id: str
    candidate_run_id: str
    baseline_failure_rate: float
    candidate_failure_rate: float
    overall_delta: float
    overall_status: str
    category_deltas: List[CategoryDeltaV2]
