"""
Tests for evaluators/llm_judge.py — _parse_response and evaluate().
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from evaluators.llm_judge import LLMJudge


class TestParseResponse:
    def setup_method(self):
        self.judge = LLMJudge()

    def test_valid_json_returns_score_and_reason(self):
        score, reason = self.judge._parse_response('{"score": 0.8, "reasoning": "good response"}')
        assert score == 0.8
        assert reason == "good response"

    def test_score_clamped_below_zero(self):
        score, _ = self.judge._parse_response('{"score": -0.5}')
        assert score == 0.0

    def test_score_clamped_above_one(self):
        score, _ = self.judge._parse_response('{"score": 1.5}')
        assert score == 1.0

    def test_markdown_code_block_stripped(self):
        raw = '```json\n{"score": 0.7, "reasoning": "ok"}\n```'
        score, reason = self.judge._parse_response(raw)
        assert score == 0.7
        assert reason == "ok"

    def test_regex_fallback_when_json_invalid(self):
        # Not valid JSON but contains score pattern
        raw = '"score": 0.6, extra garbage that prevents json parse'
        score, reason = self.judge._parse_response(raw)
        assert score == 0.6
        assert reason is None

    def test_returns_none_none_when_completely_unparseable(self):
        score, reason = self.judge._parse_response("completely invalid text with no score")
        assert score is None
        assert reason is None

    def test_missing_reasoning_defaults_to_empty_string(self):
        score, reason = self.judge._parse_response('{"score": 0.5}')
        assert score == 0.5
        assert reason == ""

    def test_score_boundary_zero(self):
        score, _ = self.judge._parse_response('{"score": 0.0}')
        assert score == 0.0

    def test_score_boundary_one(self):
        score, _ = self.judge._parse_response('{"score": 1.0}')
        assert score == 1.0


class TestLLMJudgeEvaluate:
    @pytest.mark.asyncio
    async def test_evaluate_returns_score_and_reason_on_success(self, sample_test_case):
        judge = LLMJudge()

        mock_msg = MagicMock()
        mock_msg.content = '{"score": 0.9, "reasoning": "correct and cited"}'
        mock_result = MagicMock()
        mock_result.choices = [MagicMock(message=mock_msg)]

        with patch("evaluators.llm_judge.litellm.acompletion", new=AsyncMock(return_value=mock_result)):
            score, reason = await judge.evaluate(sample_test_case, "Revenue was $1.2B [1].")

        assert score == 0.9
        assert reason == "correct and cited"

    @pytest.mark.asyncio
    async def test_evaluate_returns_none_none_on_exception(self, sample_test_case):
        judge = LLMJudge()

        with patch("evaluators.llm_judge.litellm.acompletion", new=AsyncMock(side_effect=Exception("API error"))):
            score, reason = await judge.evaluate(sample_test_case, "some response")

        assert score is None
        assert reason is None

    @pytest.mark.asyncio
    async def test_evaluate_clamps_out_of_range_score(self, sample_test_case):
        judge = LLMJudge()

        mock_msg = MagicMock()
        mock_msg.content = '{"score": 2.0, "reasoning": "over the top"}'
        mock_result = MagicMock()
        mock_result.choices = [MagicMock(message=mock_msg)]

        with patch("evaluators.llm_judge.litellm.acompletion", new=AsyncMock(return_value=mock_result)):
            score, reason = await judge.evaluate(sample_test_case, "response")

        assert score == 1.0
