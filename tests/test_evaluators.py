"""
Deterministic evaluator tests — 3+ per failure category.
Uses only in-process logic (no LLM calls).
"""
import pytest
from core.models import FailureCategory, PerturbationType, TestCase, ValidatorSpec
from evaluators.deterministic import DeterministicEvaluator


@pytest.fixture
def ev():
    return DeterministicEvaluator()


def make_tc(
    category,
    system_prompt="",
    chunks=None,
    history=None,
    query="What is X?",
    validators=None,
):
    return TestCase(
        name="test",
        failure_category=category,
        perturbation_type=PerturbationType.CHUNK_SHUFFLE,
        system_prompt=system_prompt,
        chunks=chunks or ["X is 42.", "Y is 100."],
        conversation_history=history or [],
        user_query=query,
        expected_behavior="answer correctly",
        validators=validators or [],
    )


# ── instruction_loss ──────────────────────────────────────────────────────────

class TestInstructionLoss:
    def test_detects_missing_citations(self, ev):
        tc = make_tc(FailureCategory.INSTRUCTION_LOSS,
                     system_prompt="Always cite sources using [1], [2] format.")
        score, reason = ev.evaluate(tc, "X is 42.")
        assert score < 0.7
        assert "citation" in reason.lower()

    def test_passes_with_citations(self, ev):
        tc = make_tc(FailureCategory.INSTRUCTION_LOSS,
                     system_prompt="Always cite sources using [1], [2] format.")
        score, _ = ev.evaluate(tc, "X is 42 [1].")
        assert score >= 0.7

    def test_detects_word_limit_violation(self, ev):
        tc = make_tc(FailureCategory.INSTRUCTION_LOSS,
                     system_prompt="Answer in maximum 5 words.")
        score, reason = ev.evaluate(tc, "X is forty-two and that is the correct answer for this test question.")
        assert score < 0.8
        assert "word limit" in reason.lower() or "exceed" in reason.lower()

    def test_passes_within_word_limit(self, ev):
        tc = make_tc(FailureCategory.INSTRUCTION_LOSS,
                     system_prompt="Answer in maximum 10 words.")
        score, _ = ev.evaluate(tc, "X is 42.")
        assert score >= 0.7

    def test_detects_forbidden_topic_mention(self, ev):
        tc = make_tc(FailureCategory.INSTRUCTION_LOSS,
                     system_prompt="Never mention competitor products like FooCorp.")
        score, reason = ev.evaluate(tc, "Unlike FooCorp, our product excels here.")
        assert score < 0.9

    def test_detects_missing_bullet_format(self, ev):
        tc = make_tc(FailureCategory.INSTRUCTION_LOSS,
                     system_prompt="Always respond with a bullet list.")
        score, reason = ev.evaluate(tc, "X is 42 and Y is 100.")
        assert score < 0.9
        assert reason is not None

    def test_passes_with_bullet_list(self, ev):
        tc = make_tc(FailureCategory.INSTRUCTION_LOSS,
                     system_prompt="Always respond with a bullet list.")
        score, _ = ev.evaluate(tc, "• X is 42\n• Y is 100")
        assert score >= 0.7


# ── retrieval_overshadowing ───────────────────────────────────────────────────

class TestRetrievalOvershadowing:
    CHUNKS = [
        "The quarterly revenue was $1.2 billion for the fiscal period ending September.",
        "Operating margins expanded substantially across all business segments globally.",
        "Customer acquisition costs declined meaningfully due to improved efficiency.",
    ]

    def test_flags_verbatim_parroting(self, ev):
        # Response just regurgitates all chunk text, ignores the specific question
        tc = make_tc(FailureCategory.RETRIEVAL_OVERSHADOWING,
                     chunks=self.CHUNKS, query="What was the operating margin improvement?")
        # Response talks about everything EXCEPT the question topic
        response = ("The quarterly revenue was 1.2 billion for the fiscal period. "
                    "Operating margins expanded substantially. Customer acquisition costs declined.")
        score, reason = ev.evaluate(tc, response)
        # High verbatim overlap + borderline query coverage = below par score
        assert score < 0.8

    def test_flags_low_query_coverage(self, ev):
        tc = make_tc(FailureCategory.RETRIEVAL_OVERSHADOWING,
                     chunks=self.CHUNKS,
                     query="How many new customers were acquired this quarter?")
        response = "The revenue was strong and margins expanded in the period."
        score, reason = ev.evaluate(tc, response)
        assert score < 0.6
        assert reason is not None

    def test_passes_direct_answer(self, ev):
        tc = make_tc(FailureCategory.RETRIEVAL_OVERSHADOWING,
                     chunks=self.CHUNKS,
                     query="What was the revenue?")
        response = "The quarterly revenue reached $1.2 billion for the fiscal period."
        score, _ = ev.evaluate(tc, response)
        assert score >= 0.6

    def test_passes_when_query_addressed(self, ev):
        tc = make_tc(FailureCategory.RETRIEVAL_OVERSHADOWING,
                     chunks=self.CHUNKS,
                     query="Did operating margins expand or contract?")
        response = "Operating margins expanded substantially across all business segments."
        score, _ = ev.evaluate(tc, response)
        assert score >= 0.6


# ── position_bias ─────────────────────────────────────────────────────────────

class TestPositionBias:
    def test_flags_requires_cross_run(self, ev):
        tc = make_tc(FailureCategory.POSITION_BIAS,
                     chunks=["Chunk A facts.", "Chunk B facts.", "Chunk C facts."])
        score, reason = ev.evaluate(tc, "Chunk A facts were relevant.")
        # Always flags as needing cross-run; score in ambiguous zone
        assert reason is not None
        assert "cross-run" in reason.lower() or "position bias" in reason.lower()

    def test_score_is_in_ambiguous_zone(self, ev):
        tc = make_tc(FailureCategory.POSITION_BIAS,
                     chunks=["First chunk.", "Middle chunk.", "Last chunk."])
        score, _ = ev.evaluate(tc, "First chunk was mentioned.")
        # Position bias is ambiguous by design — score stays in [0.3, 0.7] range
        assert 0.3 <= score <= 0.7

    def test_flags_uncovered_middle_chunks(self, ev):
        tc = make_tc(FailureCategory.POSITION_BIAS,
                     chunks=[
                         "Revenue was strong.",
                         "Profitability margins expanded meaningfully.",
                         "Cash flow generation was robust.",
                     ])
        # Response only covers first and last — ignores middle
        score, reason = ev.evaluate(tc, "Revenue was strong and cash flow was robust.")
        assert reason is not None


# ── answer_truncation ─────────────────────────────────────────────────────────

class TestAnswerTruncation:
    def test_detects_empty_response(self, ev):
        tc = make_tc(FailureCategory.ANSWER_TRUNCATION)
        score, _ = ev.evaluate(tc, "")
        assert score == 0.0

    def test_detects_short_response(self, ev):
        tc = make_tc(FailureCategory.ANSWER_TRUNCATION)
        score, _ = ev.evaluate(tc, "X is")
        assert score < 0.5

    def test_passes_complete_response(self, ev):
        tc = make_tc(FailureCategory.ANSWER_TRUNCATION)
        score, _ = ev.evaluate(tc, "X is 42, which is the answer based on the context.")
        assert score >= 0.8

    def test_detects_ellipsis_truncation(self, ev):
        tc = make_tc(FailureCategory.ANSWER_TRUNCATION)
        score, reason = ev.evaluate(tc, "The answer is based on the provided context...")
        assert score < 0.6
        assert reason is not None

    def test_detects_insufficient_for_multi_chunk(self, ev):
        chunks = ["Fact A.", "Fact B.", "Fact C.", "Fact D."]
        tc = make_tc(FailureCategory.ANSWER_TRUNCATION, chunks=chunks,
                     query="Summarize all the key points.")
        # Too short given 4 chunks
        score, reason = ev.evaluate(tc, "Fact A.")
        assert score < 0.6

    def test_passes_multi_chunk_response(self, ev):
        chunks = ["Fact A.", "Fact B.", "Fact C."]
        tc = make_tc(FailureCategory.ANSWER_TRUNCATION, chunks=chunks)
        response = ("The context covers several key points. Fact A is noted. "
                    "Fact B is also important. Fact C rounds out the picture.")
        score, _ = ev.evaluate(tc, response)
        assert score >= 0.7


# ── multi_turn_memory_decay ───────────────────────────────────────────────────

class TestMultiTurnMemoryDecay:
    def test_passes_with_no_history(self, ev):
        tc = make_tc(FailureCategory.MULTI_TURN_MEMORY_DECAY, history=[])
        score, _ = ev.evaluate(tc, "X is 42.")
        assert score == 1.0

    def test_flags_alien_numbers_vs_history(self, ev):
        history = [
            {"role": "user", "content": "What was the revenue?"},
            {"role": "assistant", "content": "Revenue was $1.2 billion last quarter."},
        ]
        tc = make_tc(FailureCategory.MULTI_TURN_MEMORY_DECAY,
                     chunks=["Revenue confirmed at $1.2 billion."],
                     history=history,
                     query="Can you confirm the revenue figure?")
        # Response introduces completely different numbers not in history or context
        score, reason = ev.evaluate(
            tc, "Revenue was $5.7 billion, and EBITDA was $890 million with 73% margins."
        )
        assert score < 0.7

    def test_passes_consistent_with_history(self, ev):
        history = [
            {"role": "user", "content": "What was Q3 revenue?"},
            {"role": "assistant", "content": "Q3 revenue was $1.2 billion."},
        ]
        tc = make_tc(FailureCategory.MULTI_TURN_MEMORY_DECAY,
                     chunks=["Q3 revenue was $1.2 billion."],
                     history=history,
                     query="Can you reconfirm the Q3 revenue?")
        score, _ = ev.evaluate(tc, "Q3 revenue was $1.2 billion as previously discussed.")
        assert score >= 0.7

    def test_flags_contradiction_signals(self, ev):
        history = [
            {"role": "user", "content": "Is the product available?"},
            {"role": "assistant", "content": "Yes, the product launched in March."},
        ]
        tc = make_tc(FailureCategory.MULTI_TURN_MEMORY_DECAY,
                     history=history,
                     query="When did the product launch?")
        score, reason = ev.evaluate(tc, "Actually, no, the product has not launched yet.")
        assert score <= 0.7


# ── contradiction_long_context ────────────────────────────────────────────────

class TestContradiction:
    def test_detects_unacknowledged_conflict(self, ev):
        tc = make_tc(FailureCategory.CONTRADICTION_LONG_CONTEXT,
                     chunks=["Revenue grew 15%.", "[CONFLICTING DATA] Revenue fell 85%."])
        score, reason = ev.evaluate(tc, "Revenue grew 15% this quarter.")
        assert score < 0.6

    def test_passes_when_conflict_acknowledged(self, ev):
        tc = make_tc(FailureCategory.CONTRADICTION_LONG_CONTEXT,
                     chunks=["Revenue grew 15%.", "[CONFLICTING DATA] Revenue fell 85%."])
        score, _ = ev.evaluate(tc, "The context contains contradictory data on revenue.")
        assert score >= 0.7

    def test_detects_directional_contradiction_in_response(self, ev):
        tc = make_tc(FailureCategory.CONTRADICTION_LONG_CONTEXT,
                     chunks=["Revenue data was mixed."])
        # Response simultaneously claims increased 15% and decreased 15%
        response = "Revenue increased 15% in Q1. However, revenue decreased 15% overall."
        score, reason = ev.evaluate(tc, response)
        assert score < 0.5

    def test_passes_unambiguous_claim(self, ev):
        tc = make_tc(FailureCategory.CONTRADICTION_LONG_CONTEXT,
                     chunks=["Revenue grew 15% year over year."])
        score, _ = ev.evaluate(tc, "Revenue grew 15% year over year, per the report.")
        assert score >= 0.8

    def test_passes_acknowledged_tension(self, ev):
        tc = make_tc(FailureCategory.CONTRADICTION_LONG_CONTEXT,
                     chunks=["Q1 results were strong.", "Q2 results disappointed."])
        score, _ = ev.evaluate(
            tc, "On one hand Q1 was strong, on the other hand Q2 was disappointing."
        )
        assert score >= 0.7


# ── citation_drift ────────────────────────────────────────────────────────────

class TestCitationDrift:
    def test_flags_out_of_range_citations(self, ev):
        tc = make_tc(FailureCategory.CITATION_DRIFT,
                     chunks=["chunk1", "chunk2"],
                     system_prompt="Cite using [N] format.")
        score, reason = ev.evaluate(tc, "See reference [5] for details.")
        assert score < 0.5

    def test_passes_valid_citations(self, ev):
        tc = make_tc(FailureCategory.CITATION_DRIFT,
                     chunks=["Revenue is $1B.", "Margin is 24%."])
        score, _ = ev.evaluate(tc, "Revenue is $1B [1] and margin is 24% [2].")
        assert score >= 0.7

    def test_flags_no_citations_when_required(self, ev):
        tc = make_tc(FailureCategory.CITATION_DRIFT,
                     chunks=["Revenue data here."],
                     system_prompt="Always cite sources using [1] notation.")
        score, reason = ev.evaluate(tc, "Revenue was strong this quarter.")
        assert score < 0.5
        assert reason is not None

    def test_passes_no_citations_without_requirement(self, ev):
        tc = make_tc(FailureCategory.CITATION_DRIFT,
                     chunks=["Revenue data here."],
                     system_prompt="Be helpful.")
        score, _ = ev.evaluate(tc, "Revenue was strong this quarter.")
        # No citation requirement → ambiguous, not a hard fail
        assert score >= 0.5

    def test_flags_citation_content_drift(self, ev):
        # [1] attached to a sentence that shares zero words with chunk 1
        tc = make_tc(FailureCategory.CITATION_DRIFT,
                     chunks=["Revenue reached one billion dollars.", "Margins were positive."],
                     system_prompt="Cite sources.")
        # Sentence about weather citing chunk 1 about revenue — clear drift
        response = ("The weather forecast predicts sunny skies tomorrow morning [1]. "
                    "Temperatures will be mild this weekend [2].")
        score, reason = ev.evaluate(tc, response)
        assert score < 0.7


# ── hallucination_overload ────────────────────────────────────────────────────

class TestHallucinationOverload:
    def test_flags_alien_numbers(self, ev):
        tc = make_tc(FailureCategory.HALLUCINATION_OVERLOAD,
                     chunks=["Revenue was $500 million."])
        response = ("Revenue was $500 million. Also profit margin was 73% and "
                    "EBITDA was $892 billion and headcount is 45000.")
        score, reason = ev.evaluate(tc, response)
        assert score < 0.8

    def test_passes_grounded_response(self, ev):
        tc = make_tc(FailureCategory.HALLUCINATION_OVERLOAD,
                     chunks=["Revenue was $500 million."])
        score, _ = ev.evaluate(tc, "Revenue was $500 million per the report.")
        assert score >= 0.8

    def test_passes_within_ten_percent_tolerance(self, ev):
        # $505 million is within 10% of $500 million → should pass
        tc = make_tc(FailureCategory.HALLUCINATION_OVERLOAD,
                     chunks=["Revenue was $500 million."])
        score, _ = ev.evaluate(tc, "Revenue was approximately $505 million.")
        assert score >= 0.7

    def test_flags_outside_ten_percent_tolerance(self, ev):
        # $800 million is ~60% off from $500 million → should flag
        tc = make_tc(FailureCategory.HALLUCINATION_OVERLOAD,
                     chunks=["Revenue was $500 million."])
        score, reason = ev.evaluate(
            tc, "Revenue was $800 million and EBITDA hit $350 million this quarter."
        )
        assert score < 0.8

    def test_passes_no_numeric_claims(self, ev):
        tc = make_tc(FailureCategory.HALLUCINATION_OVERLOAD,
                     chunks=["The company performed well."])
        score, _ = ev.evaluate(tc, "The company performed well this quarter.")
        assert score >= 0.8

    def test_flags_alien_named_entities(self, ev):
        tc = make_tc(FailureCategory.HALLUCINATION_OVERLOAD,
                     chunks=["The company expanded its product line."])
        score, reason = ev.evaluate(
            tc,
            "The company, led by John Smith and Sarah Johnson and Michael Brown, expanded its line.",
        )
        # Three named entities not in context
        assert score < 0.9


# ── custom validators ─────────────────────────────────────────────────────────

class TestCustomValidators:
    def test_contains_pattern_validator(self, ev):
        tc = make_tc(FailureCategory.INSTRUCTION_LOSS,
                     validators=[ValidatorSpec(type="contains_pattern", pattern=r"\d+%")])
        assert ev.evaluate(tc, "Growth was 15%.")[0] > ev.evaluate(tc, "Growth was high.")[0]

    def test_min_length_validator(self, ev):
        tc = make_tc(FailureCategory.ANSWER_TRUNCATION,
                     validators=[ValidatorSpec(type="min_length", value=50)])
        short_score, _ = ev.evaluate(tc, "Short.")
        long_score, _ = ev.evaluate(
            tc, "This is a much longer answer that definitely exceeds fifty characters total."
        )
        assert long_score > short_score

    def test_not_contains_validator(self, ev):
        tc = make_tc(FailureCategory.INSTRUCTION_LOSS,
                     validators=[ValidatorSpec(type="not_contains", pattern="I don't know")])
        fail_score, _ = ev.evaluate(tc, "I don't know the answer.")
        pass_score, _ = ev.evaluate(tc, "The answer is X.")
        assert pass_score > fail_score

    def test_ends_with_punctuation_validator(self, ev):
        tc = make_tc(FailureCategory.ANSWER_TRUNCATION,
                     validators=[ValidatorSpec(type="ends_with_punctuation")])
        bad_score, _ = ev.evaluate(tc, "The answer is something")
        good_score, _ = ev.evaluate(tc, "The answer is something.")
        assert good_score > bad_score

    def test_contains_all_validator(self, ev):
        tc = make_tc(FailureCategory.INSTRUCTION_LOSS,
                     validators=[ValidatorSpec(type="contains_all", value=["revenue", "margin"])])
        partial, _ = ev.evaluate(tc, "Revenue was strong.")
        full, _ = ev.evaluate(tc, "Revenue was strong and margin improved.")
        assert full > partial
