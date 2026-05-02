from __future__ import annotations

import json
import re
from typing import Optional, Tuple

import litellm

from core.models import TestCase

_JUDGE_PROMPT = """You are a strict reliability evaluator for LLM-powered RAG systems.

## Task
Evaluate whether the model response correctly handles the context, instructions, and query.
Focus specifically on the failure category: **{failure_category}**

## Expected behavior
{expected_behavior}

## System prompt given to the model
{system_prompt}

## Context chunks provided to the model
{chunks}

## User query
{query}

## Model response to evaluate
{response}

## Scoring
Rate from 0.0 to 1.0:
- 1.0 = Fully correct, follows all instructions, no failure detected
- 0.7 = Minor issues but mostly correct
- 0.5 = Partial failure
- 0.3 = Significant failure with a few correct elements
- 0.0 = Complete failure

Be strict. Pay special attention to the {failure_category} failure mode.

Respond with ONLY valid JSON, no markdown:
{{"score": <float 0.0-1.0>, "reasoning": "<one or two sentences>"}}"""


class LLMJudge:
    """Semantic evaluator — only called when deterministic score is ambiguous (0.3–0.7).

    Returns (score, reasoning) so the runner can store both and track disputes.
    """

    def __init__(self, judge_model: str = "claude-opus-4-5"):
        self.judge_model = judge_model

    async def evaluate(
        self, test_case: TestCase, response: str
    ) -> Tuple[Optional[float], Optional[str]]:
        chunks_fmt = "\n".join(
            f"[Chunk {i + 1}] {c}" for i, c in enumerate(test_case.chunks)
        )
        prompt = _JUDGE_PROMPT.format(
            failure_category=test_case.failure_category.value,
            expected_behavior=test_case.expected_behavior,
            system_prompt=test_case.system_prompt,
            chunks=chunks_fmt,
            query=test_case.user_query,
            response=response,
        )
        try:
            result = await litellm.acompletion(
                model=self.judge_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
                temperature=0,
            )
            raw = result.choices[0].message.content.strip()
            return self._parse_response(raw)
        except Exception:
            return None, None

    def _parse_response(self, raw: str) -> Tuple[Optional[float], Optional[str]]:
        raw = re.sub(r"```(?:json)?", "", raw).strip()
        try:
            data = json.loads(raw)
            score = max(0.0, min(1.0, float(data["score"])))
            reasoning = data.get("reasoning", "")
            return score, reasoning
        except (json.JSONDecodeError, KeyError, ValueError):
            match = re.search(r'"score"\s*:\s*([0-9.]+)', raw)
            if match:
                return max(0.0, min(1.0, float(match.group(1)))), None
            return None, None
