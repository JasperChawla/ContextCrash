from __future__ import annotations

import asyncio
import random
import time
import uuid
from typing import Dict, List, Optional

import litellm
from tenacity import retry, stop_after_attempt, wait_exponential

from core.models import (
    DepthScore,
    FailureCategory,
    ModelCostSummary,
    RunConfig,
    RunSummary,
    TestCase,
    TestResult,
)
from core.storage import ResultStorage
from evaluators import DeterministicEvaluator, LLMJudge, build_summary

litellm.suppress_debug_info = True

# Per-1M-token pricing (input_usd, output_usd).
# These are ballpark figures — exact pricing varies by tier/region.
_PRICE_PER_1M: Dict[str, tuple] = {
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-haiku-4-5": (0.80, 4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-opus-4-5": (15.00, 75.00),
    "claude-opus-4-7": (15.00, 75.00),
    "gpt-4o": (5.00, 15.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gemini/gemini-1.5-pro": (3.50, 10.50),
    "gemini/gemini-1.5-flash": (0.075, 0.30),
    "gemini/gemini-flash": (0.075, 0.30),
    "gemini/gemini-2.0-flash": (0.075, 0.30),
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    key = model.lower()
    for m, (inp_price, out_price) in _PRICE_PER_1M.items():
        if m in key:
            return (prompt_tokens * inp_price + completion_tokens * out_price) / 1_000_000
    # Unknown model — use gpt-4o-mini as conservative baseline
    return (prompt_tokens * 0.15 + completion_tokens * 0.60) / 1_000_000


class TestRunner:
    def __init__(self, config: RunConfig, storage: ResultStorage):
        self.config = config
        self.storage = storage
        self.det_evaluator = DeterministicEvaluator()
        self.llm_judge = LLMJudge(config.judge_model)
        # Semaphore prevents thundering herd against rate-limited APIs
        self.semaphore = asyncio.Semaphore(config.parallel_workers)

    async def run_suite(self, run_id: Optional[str] = None) -> Dict[str, RunSummary]:
        run_id = run_id or str(uuid.uuid4())
        self.storage.create_run(run_id, self.config.suite_name, self.config.models)

        summaries: Dict[str, RunSummary] = {}
        for model in self.config.models:
            results = await self._run_model(run_id, model)
            summary = build_summary(run_id, self.config.suite_name, model, results)
            self.storage.save_summary(summary)
            # ITEM 3 — persist per-category cost breakdown
            self._save_cost_summaries(run_id, model, results)
            summaries[model] = summary

        return summaries

    async def _run_model(self, run_id: str, model: str) -> List[TestResult]:
        tasks = [self._run_single(run_id, model, tc) for tc in self.config.test_cases]
        results = await asyncio.gather(*tasks)

        # ITEM 4 — kick off depth-level runs for test cases that have depth levels configured
        depth_tasks = [
            self._run_depth_levels(run_id, model, tc)
            for tc in self.config.test_cases
            if tc.context_depth_levels
        ]
        if depth_tasks:
            await asyncio.gather(*depth_tasks)

        return list(results)

    async def _run_single(self, run_id: str, model: str, tc: TestCase) -> TestResult:
        async with self.semaphore:
            messages = self._build_messages(tc)
            start = time.monotonic()
            try:
                resp = await self._call_model(model, messages)
                response_text = resp.choices[0].message.content or ""
                usage = resp.usage or None
                prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                completion_tokens = getattr(usage, "completion_tokens", 0) or 0
                total_tokens = getattr(usage, "total_tokens", 0) or (prompt_tokens + completion_tokens)
            except Exception as e:
                response_text = f"[MODEL ERROR: {e}]"
                prompt_tokens = completion_tokens = total_tokens = 0
            latency = (time.monotonic() - start) * 1000

            # ITEM 3 — try litellm's built-in cost function, fall back to our table
            try:
                cost = litellm.completion_cost(completion_response=resp)  # type: ignore
            except Exception:
                cost = _estimate_cost(model, prompt_tokens, completion_tokens)

            det_score, det_reason = self.det_evaluator.evaluate(tc, response_text)

            # Position bias always needs cross-run comparison — skip the judge
            skip_judge = tc.failure_category == FailureCategory.POSITION_BIAS

            # ITEM 2 — only call judge in the ambiguous band, skip for position bias
            llm_score: Optional[float] = None
            judge_reason: Optional[str] = None
            disputed = False
            lo, hi = self.config.failure_threshold - 0.2, self.config.failure_threshold + 0.2
            if not skip_judge and lo <= det_score <= hi:
                llm_score, judge_reason = await self.llm_judge.evaluate(tc, response_text)
                if llm_score is not None:
                    disputed = abs(det_score - llm_score) > 0.3

            final_score = llm_score if llm_score is not None else det_score

            result = TestResult(
                run_id=run_id,
                test_case_id=tc.id,
                test_name=tc.name,
                failure_category=tc.failure_category.value,
                perturbation_type=tc.perturbation_type.value,
                model=model,
                response=response_text,
                deterministic_score=det_score,
                llm_judge_score=llm_score,
                final_score=final_score,
                failed=final_score < self.config.failure_threshold,
                failure_reason=det_reason if final_score < self.config.failure_threshold else None,
                judge_rule_disagreement=disputed,  # backward compat
                disputed=disputed,
                deterministic_reason=det_reason,
                judge_reason=judge_reason,
                latency_ms=latency,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                tokens_used=total_tokens,
                estimated_cost_usd=cost,
            )
            await self.storage.save_result(result)
            return result

    # ITEM 4 — run same test at each context depth for degradation curve
    async def _run_depth_levels(self, run_id: str, model: str, tc: TestCase) -> None:
        for depth in tc.context_depth_levels:
            n_chunks = max(1, round(len(tc.chunks) * depth))
            shallow_tc = tc.model_copy(update={"chunks": tc.chunks[:n_chunks]})

            async with self.semaphore:
                messages = self._build_messages(shallow_tc)
                try:
                    resp = await self._call_model(model, messages)
                    response_text = resp.choices[0].message.content or ""
                except Exception:
                    response_text = ""

                det_score, _ = self.det_evaluator.evaluate(shallow_tc, response_text)
                depth_score = DepthScore(
                    run_id=run_id,
                    test_case_id=tc.id,
                    model=model,
                    depth_level=depth,
                    score=det_score,
                    failure_category=tc.failure_category.value,
                    failed=det_score < self.config.failure_threshold,
                )
                await self.storage.save_depth_score(depth_score)

    # ITEM 3 — break down cost by failure category for comparison table
    def _save_cost_summaries(
        self, run_id: str, model: str, results: List[TestResult]
    ) -> None:
        from collections import defaultdict
        by_cat: Dict[str, List[TestResult]] = defaultdict(list)
        for r in results:
            by_cat[r.failure_category].append(r)

        for cat, rs in by_cat.items():
            summary = ModelCostSummary(
                run_id=run_id,
                model=model,
                failure_category=cat,
                failure_rate=sum(1 for r in rs if r.failed) / len(rs),
                avg_score=sum(r.final_score for r in rs) / len(rs),
                estimated_cost_usd=sum(r.estimated_cost_usd for r in rs),
                test_count=len(rs),
            )
            self.storage.save_model_cost_summary(summary)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
    async def _call_model(self, model: str, messages: list):
        return await litellm.acompletion(
            model=model, messages=messages, max_tokens=2048, timeout=60
        )

    def _build_messages(self, tc: TestCase) -> list:
        # ITEM 6 — test-level ordering overrides suite-level default
        ordering = tc.chunk_ordering or self.config.chunk_ordering
        chunks = self._apply_ordering(tc.chunks, ordering)

        context_blocks = "\n\n".join(
            f"[Chunk {i + 1}]\n{chunk}" for i, chunk in enumerate(chunks)
        )
        system_content = f"{tc.system_prompt}\n\n---\nRetrieved Context:\n{context_blocks}"
        messages = [{"role": "system", "content": system_content}]
        messages.extend(tc.conversation_history)
        messages.append({"role": "user", "content": tc.user_query})
        return messages

    # ITEM 6 — apply chunk ordering before building messages
    @staticmethod
    def _apply_ordering(chunks: List[str], ordering: str) -> List[str]:
        if ordering == "reversed":
            return list(reversed(chunks))
        if ordering == "random":
            shuffled = chunks[:]
            random.shuffle(shuffled)
            return shuffled
        return chunks  # sequential = default, no-op
