from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    INSTRUCTION_LOSS = "instruction_loss"
    RETRIEVAL_OVERSHADOWING = "retrieval_overshadowing"
    POSITION_BIAS = "position_bias"
    ANSWER_TRUNCATION = "answer_truncation"
    MULTI_TURN_MEMORY_DECAY = "multi_turn_memory_decay"
    CONTRADICTION_LONG_CONTEXT = "contradiction_long_context"
    CITATION_DRIFT = "citation_drift"
    HALLUCINATION_OVERLOAD = "hallucination_overload"


class PerturbationType(str, Enum):
    CHUNK_SHUFFLE = "chunk_shuffle"
    DISTRACTOR_INJECTION = "distractor_injection"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    INSTRUCTION_BURIAL = "instruction_burial"
    HISTORY_CONTAMINATION = "history_contamination"
    PARAPHRASE_EVIDENCE = "paraphrase_evidence"


# ITEM 6 — chunk ordering type alias used by both RunConfig and TestCase
ChunkOrdering = Literal["sequential", "random", "reversed"]


class ValidatorSpec(BaseModel):
    type: str
    pattern: Optional[str] = None
    value: Optional[Any] = None
    description: Optional[str] = None
    weight: float = 1.0


class TestCase(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    failure_category: FailureCategory
    perturbation_type: PerturbationType
    system_prompt: str
    chunks: List[str]
    conversation_history: List[Dict[str, str]] = []
    user_query: str
    expected_behavior: str
    validators: List[ValidatorSpec] = []
    metadata: Dict[str, Any] = {}
    # ITEM 4 — depth levels for degradation curves (empty = skip depth runs)
    context_depth_levels: List[float] = []
    # ITEM 6 — per-test chunk ordering override (None = use RunConfig default)
    chunk_ordering: Optional[ChunkOrdering] = None


class TestResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    test_case_id: str
    test_name: str
    failure_category: str
    perturbation_type: str
    model: str
    response: str
    deterministic_score: Optional[float] = None
    llm_judge_score: Optional[float] = None
    final_score: float
    failed: bool
    failure_reason: Optional[str] = None
    # ITEM 2 — explicit dispute fields (judge_rule_disagreement kept for compat)
    judge_rule_disagreement: bool = False
    disputed: bool = False
    deterministic_reason: Optional[str] = None
    judge_reason: Optional[str] = None
    latency_ms: float
    # ITEM 3 — separate token counts for cost estimation
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tokens_used: int = 0
    estimated_cost_usd: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RunConfig(BaseModel):
    suite_name: str
    models: List[str]
    test_cases: List[TestCase]
    judge_model: str = "claude-opus-4-5"
    parallel_workers: int = 5
    db_path: str = "./data/results.duckdb"
    failure_threshold: float = 0.5
    # ITEM 6 — retrieval pipeline knobs (suite-level defaults)
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 5
    reranking_enabled: bool = False
    chunk_ordering: ChunkOrdering = "sequential"


class RunSummary(BaseModel):
    run_id: str
    suite_name: str
    model: str
    total_tests: int
    failed_tests: int
    failure_rate: float
    failure_by_category: Dict[str, float]
    avg_latency_ms: float
    judge_disagreement_rate: float
    # ITEM 2 — explicit dispute count
    disputed_count: int = 0
    # ITEM 3 — estimated run cost
    total_cost_usd: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ComparisonResult(BaseModel):
    baseline_run_id: str
    candidate_run_id: str
    model: str
    overall_delta: float
    delta_by_category: Dict[str, float]
    regressions: List[str]
    improvements: List[str]


# ITEM 3 — per-model, per-category cost/performance breakdown stored after each run
class ModelCostSummary(BaseModel):
    run_id: str
    model: str
    failure_category: str
    failure_rate: float
    avg_score: float
    estimated_cost_usd: float
    test_count: int


# ITEM 4 — single score reading at one context depth level
class DepthScore(BaseModel):
    run_id: str
    test_case_id: str
    model: str
    depth_level: float
    score: float
    failure_category: str
    failed: bool
