"""
Runner tests use mocked LiteLLM calls - we're testing orchestration logic,
not actual model responses. The evaluator tests cover scoring correctness.
"""
import asyncio
import pytest
import duckdb
from unittest.mock import AsyncMock, MagicMock, patch

from core.models import FailureCategory, PerturbationType, RunConfig, TestCase, TestResult
from core.runner import TestRunner
from core.storage import ResultStorage, _EXPECTED_TEST_RESULT_COLS, _EXPECTED_RUN_SUMMARY_COLS


def make_config(tmp_db, test_cases=None):
    if test_cases is None:
        test_cases = [
            TestCase(
                name="mock_test",
                failure_category=FailureCategory.INSTRUCTION_LOSS,
                perturbation_type=PerturbationType.CHUNK_SHUFFLE,
                system_prompt="Always cite using [1].",
                chunks=["Revenue was $1B."],
                user_query="What was revenue?",
                expected_behavior="Should cite sources.",
            )
        ]
    return RunConfig(
        suite_name="test_suite",
        models=["gpt-4o"],
        test_cases=test_cases,
        db_path=tmp_db,
        parallel_workers=2,
    )


class MockUsage:
    total_tokens = 100


class MockMessage:
    content = "Revenue was $1B [1]."


class MockChoice:
    message = MockMessage()


class MockResponse:
    choices = [MockChoice()]
    usage = MockUsage()


@pytest.mark.asyncio
async def test_run_suite_creates_summary(temp_db):
    config = make_config(temp_db)
    storage = ResultStorage(temp_db)
    runner = TestRunner(config, storage)

    with patch.object(runner, "_call_model", new=AsyncMock(return_value=MockResponse())):
        summaries = await runner.run_suite("test-run-001")

    assert "gpt-4o" in summaries
    summary = summaries["gpt-4o"]
    assert summary.total_tests == 1
    assert summary.run_id == "test-run-001"


@pytest.mark.asyncio
async def test_failed_model_call_doesnt_crash(temp_db):
    config = make_config(temp_db)
    storage = ResultStorage(temp_db)
    runner = TestRunner(config, storage)

    # Model throws on all retries
    with patch.object(runner, "_call_model", new=AsyncMock(side_effect=Exception("rate limited"))):
        summaries = await runner.run_suite()

    # Should still return a summary - the test records as error response
    assert "gpt-4o" in summaries
    assert summaries["gpt-4o"].total_tests == 1


@pytest.mark.asyncio
async def test_results_persisted_to_storage(temp_db):
    config = make_config(temp_db)
    storage = ResultStorage(temp_db)
    runner = TestRunner(config, storage)

    with patch.object(runner, "_call_model", new=AsyncMock(return_value=MockResponse())):
        summaries = await runner.run_suite("persist-run")

    results = storage.get_results_for_run("persist-run")
    assert len(results) == 1
    assert results[0]["model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_multiple_models_run_independently(temp_db):
    config = make_config(temp_db)
    config.models = ["gpt-4o", "claude-opus-4-5"]
    storage = ResultStorage(temp_db)
    runner = TestRunner(config, storage)

    with patch.object(runner, "_call_model", new=AsyncMock(return_value=MockResponse())):
        summaries = await runner.run_suite()

    assert "gpt-4o" in summaries
    assert "claude-opus-4-5" in summaries


def test_build_messages_includes_all_chunks():
    config = make_config(":memory:")
    storage = ResultStorage("./data/results.duckdb")
    runner = TestRunner(config, storage)

    tc = TestCase(
        name="t",
        failure_category=FailureCategory.POSITION_BIAS,
        perturbation_type=PerturbationType.CHUNK_SHUFFLE,
        system_prompt="Be helpful.",
        chunks=["Chunk A", "Chunk B", "Chunk C"],
        user_query="What do the chunks say?",
        expected_behavior="reference all chunks",
    )
    messages = runner._build_messages(tc)

    system_msg = messages[0]
    assert system_msg["role"] == "system"
    assert "Chunk A" in system_msg["content"]
    assert "Chunk B" in system_msg["content"]
    assert "Chunk C" in system_msg["content"]
    assert messages[-1]["role"] == "user"


def test_build_messages_includes_history():
    config = make_config(":memory:")
    storage = ResultStorage("./data/results.duckdb")
    runner = TestRunner(config, storage)

    history = [
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
    ]
    tc = TestCase(
        name="t",
        failure_category=FailureCategory.MULTI_TURN_MEMORY_DECAY,
        perturbation_type=PerturbationType.HISTORY_CONTAMINATION,
        system_prompt="Remember conversation.",
        chunks=["fact"],
        conversation_history=history,
        user_query="follow-up question",
        expected_behavior="reference earlier context",
    )
    messages = runner._build_messages(tc)

    roles = [m["role"] for m in messages]
    assert roles == ["system", "user", "assistant", "user"]


# ── ITEM 2: Dispute tracking ─────────────────────────────────────────────────

class TestDisputeTracking:
    @pytest.mark.asyncio
    async def test_dispute_flagged_when_judge_disagrees(self, temp_db):
        config = make_config(temp_db)
        storage = ResultStorage(temp_db)
        runner = TestRunner(config, storage)

        # det=0.5 lands in ambiguous band [0.3, 0.7]; judge=0.9 → |diff|=0.4>0.3 → disputed
        with patch.object(runner.det_evaluator, "evaluate", return_value=(0.5, "ambiguous")):
            with patch.object(runner.llm_judge, "evaluate", new=AsyncMock(return_value=(0.9, "looks good"))):
                with patch.object(runner, "_call_model", new=AsyncMock(return_value=MockResponse())):
                    await runner.run_suite("dispute-run-001")

        results = storage.get_results_for_run("dispute-run-001")
        assert len(results) == 1
        assert results[0]["disputed"] is True
        assert results[0]["judge_rule_disagreement"] is True  # backward compat field

    @pytest.mark.asyncio
    async def test_no_dispute_when_scores_agree(self, temp_db):
        config = make_config(temp_db)
        storage = ResultStorage(temp_db)
        runner = TestRunner(config, storage)

        # det=0.5, judge=0.6 → |diff|=0.1 < 0.3 → not disputed
        with patch.object(runner.det_evaluator, "evaluate", return_value=(0.5, "ambiguous")):
            with patch.object(runner.llm_judge, "evaluate", new=AsyncMock(return_value=(0.6, "close enough"))):
                with patch.object(runner, "_call_model", new=AsyncMock(return_value=MockResponse())):
                    await runner.run_suite("agree-run")

        results = storage.get_results_for_run("agree-run")
        assert results[0]["disputed"] is False

    @pytest.mark.asyncio
    async def test_position_bias_skips_judge(self, temp_db):
        tc = TestCase(
            name="pos_bias_test",
            failure_category=FailureCategory.POSITION_BIAS,
            perturbation_type=PerturbationType.CHUNK_SHUFFLE,
            system_prompt="Be helpful.",
            chunks=["a", "b", "c"],
            user_query="What do the chunks say?",
            expected_behavior="reference all chunks",
        )
        config = make_config(temp_db, [tc])
        storage = ResultStorage(temp_db)
        runner = TestRunner(config, storage)

        mock_judge = AsyncMock(return_value=(0.9, "irrelevant"))
        with patch.object(runner, "_call_model", new=AsyncMock(return_value=MockResponse())):
            with patch.object(runner.llm_judge, "evaluate", new=mock_judge):
                await runner.run_suite("pos-bias-run")

        mock_judge.assert_not_called()

    @pytest.mark.asyncio
    async def test_judge_skipped_outside_ambiguous_band(self, temp_db):
        config = make_config(temp_db)
        storage = ResultStorage(temp_db)
        runner = TestRunner(config, storage)

        # det_score=0.9 is above hi=0.7 → judge must not be called
        mock_judge = AsyncMock(return_value=(0.0, "ignore me"))
        with patch.object(runner.det_evaluator, "evaluate", return_value=(0.9, "clear pass")):
            with patch.object(runner, "_call_model", new=AsyncMock(return_value=MockResponse())):
                with patch.object(runner.llm_judge, "evaluate", new=mock_judge):
                    await runner.run_suite("skip-judge-run")

        mock_judge.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispute_count_reflected_in_summary(self, temp_db):
        config = make_config(temp_db)
        storage = ResultStorage(temp_db)
        runner = TestRunner(config, storage)

        with patch.object(runner.det_evaluator, "evaluate", return_value=(0.5, "ambiguous")):
            with patch.object(runner.llm_judge, "evaluate", new=AsyncMock(return_value=(0.9, "disagree"))):
                with patch.object(runner, "_call_model", new=AsyncMock(return_value=MockResponse())):
                    summaries = await runner.run_suite("dispute-summary-run")

        assert summaries["gpt-4o"].disputed_count == 1


# ── ITEM 4: Degradation curves ───────────────────────────────────────────────

class TestDepthLevels:
    @pytest.mark.asyncio
    async def test_depth_scores_saved_for_each_level(self, temp_db):
        tc = TestCase(
            name="depth_test",
            failure_category=FailureCategory.INSTRUCTION_LOSS,
            perturbation_type=PerturbationType.CHUNK_SHUFFLE,
            system_prompt="Be helpful.",
            chunks=["c1", "c2", "c3", "c4"],
            user_query="What?",
            expected_behavior="something",
            context_depth_levels=[0.25, 0.5, 0.75, 1.0],
        )
        config = make_config(temp_db, [tc])
        storage = ResultStorage(temp_db)
        runner = TestRunner(config, storage)

        with patch.object(runner, "_call_model", new=AsyncMock(return_value=MockResponse())):
            await runner.run_suite("depth-run-001")

        depth_data = storage.get_degradation_data("depth-run-001")
        assert len(depth_data) == 4
        assert {d["depth_level"] for d in depth_data} == {0.25, 0.5, 0.75, 1.0}

    @pytest.mark.asyncio
    async def test_no_depth_runs_when_no_depth_levels(self, temp_db):
        config = make_config(temp_db)  # default tc has no depth levels
        storage = ResultStorage(temp_db)
        runner = TestRunner(config, storage)

        with patch.object(runner, "_call_model", new=AsyncMock(return_value=MockResponse())):
            await runner.run_suite("no-depth-run")

        assert storage.get_degradation_data("no-depth-run") == []

    def test_depth_truncation_chunk_count(self):
        chunks = ["c1", "c2", "c3", "c4"]
        assert max(1, round(len(chunks) * 0.25)) == 1
        assert max(1, round(len(chunks) * 0.5)) == 2
        assert max(1, round(len(chunks) * 0.75)) == 3
        assert max(1, round(len(chunks) * 1.0)) == 4

    @pytest.mark.asyncio
    async def test_depth_model_receives_truncated_chunks(self, temp_db):
        tc = TestCase(
            name="trunc_test",
            failure_category=FailureCategory.INSTRUCTION_LOSS,
            perturbation_type=PerturbationType.CHUNK_SHUFFLE,
            system_prompt="Be helpful.",
            chunks=["alpha", "beta", "gamma", "delta"],
            user_query="What?",
            expected_behavior="something",
            context_depth_levels=[0.5],
        )
        config = make_config(temp_db, [tc])
        storage = ResultStorage(temp_db)
        runner = TestRunner(config, storage)

        captured: list = []

        async def capture_call(model, messages):
            captured.append(messages)
            return MockResponse()

        with patch.object(runner, "_call_model", side_effect=capture_call):
            await runner.run_suite("trunc-run")

        # First call = full run, second = depth=0.5 run (2 of 4 chunks)
        assert len(captured) == 2
        depth_system = captured[1][0]["content"]
        assert "alpha" in depth_system
        assert "beta" in depth_system
        assert "gamma" not in depth_system
        assert "delta" not in depth_system


# ── ITEM 6: Chunk ordering ────────────────────────────────────────────────────

class TestChunkOrdering:
    def _runner(self):
        return TestRunner(make_config(":memory:"), ResultStorage(":memory:"))

    def test_apply_ordering_sequential_is_noop(self):
        runner = self._runner()
        chunks = ["a", "b", "c"]
        assert runner._apply_ordering(chunks, "sequential") == ["a", "b", "c"]

    def test_apply_ordering_reversed(self):
        runner = self._runner()
        chunks = ["a", "b", "c"]
        assert runner._apply_ordering(chunks, "reversed") == ["c", "b", "a"]

    def test_apply_ordering_random_preserves_all_chunks(self):
        runner = self._runner()
        chunks = ["a", "b", "c", "d"]
        result = runner._apply_ordering(chunks, "random")
        assert sorted(result) == sorted(chunks)
        assert len(result) == len(chunks)

    def test_apply_ordering_random_does_not_mutate_original(self):
        runner = self._runner()
        chunks = ["a", "b", "c"]
        original = chunks[:]
        runner._apply_ordering(chunks, "random")
        assert chunks == original

    def test_build_messages_test_level_ordering_overrides_config(self):
        config = make_config(":memory:")
        config.chunk_ordering = "sequential"
        runner = TestRunner(config, ResultStorage(":memory:"))

        tc = TestCase(
            name="ordering_test",
            failure_category=FailureCategory.POSITION_BIAS,
            perturbation_type=PerturbationType.CHUNK_SHUFFLE,
            system_prompt="Be helpful.",
            chunks=["first", "second", "third"],
            user_query="What order?",
            expected_behavior="reference chunks",
            chunk_ordering="reversed",
        )
        content = runner._build_messages(tc)[0]["content"]
        # reversed: third, second, first
        assert "[Chunk 1]\nthird" in content
        assert "[Chunk 3]\nfirst" in content

    def test_build_messages_falls_back_to_config_ordering(self):
        config = make_config(":memory:")
        config.chunk_ordering = "reversed"
        runner = TestRunner(config, ResultStorage(":memory:"))

        tc = TestCase(
            name="ordering_test2",
            failure_category=FailureCategory.POSITION_BIAS,
            perturbation_type=PerturbationType.CHUNK_SHUFFLE,
            system_prompt="Be helpful.",
            chunks=["alpha", "beta", "gamma"],
            user_query="What?",
            expected_behavior="reference chunks",
            chunk_ordering=None,
        )
        content = runner._build_messages(tc)[0]["content"]
        # config says reversed: gamma, beta, alpha
        assert "[Chunk 1]\ngamma" in content
        assert "[Chunk 3]\nalpha" in content


# ── Schema regression tests ───────────────────────────────────────────────────

def test_save_result_no_column_mismatch(tmp_path):
    """Regression: TestResult with all 23 fields saves without BinderException."""
    db_path = str(tmp_path / "no_mismatch.duckdb")
    storage = ResultStorage(db_path)
    storage.create_run("r1", "suite", ["gpt-4o"])
    result = TestResult(
        run_id="r1",
        test_case_id="tc1",
        test_name="test",
        failure_category="instruction_loss",
        perturbation_type="chunk_shuffle",
        model="gpt-4o",
        response="ok",
        final_score=0.8,
        failed=False,
        latency_ms=100.0,
        prompt_tokens=50,
        completion_tokens=20,
        tokens_used=70,
        estimated_cost_usd=0.001,
    )
    asyncio.run(storage.save_result(result))
    rows = storage.get_results_for_run("r1")
    assert len(rows) == 1
    assert rows[0]["model"] == "gpt-4o"
    assert rows[0]["prompt_tokens"] == 50
    assert rows[0]["estimated_cost_usd"] == pytest.approx(0.001)


def test_stale_17col_schema_migrated_on_init(tmp_path):
    """When a DB with the old 17-column test_results exists, ResultStorage rebuilds it."""
    db_path = str(tmp_path / "stale.duckdb")

    # Simulate the old 17-column schema that caused the BinderException
    with duckdb.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE test_results (
                id                    VARCHAR PRIMARY KEY,
                run_id                VARCHAR NOT NULL,
                test_case_id          VARCHAR NOT NULL,
                test_name             VARCHAR NOT NULL,
                failure_category      VARCHAR NOT NULL,
                perturbation_type     VARCHAR NOT NULL,
                model                 VARCHAR NOT NULL,
                response              TEXT,
                deterministic_score   DOUBLE,
                llm_judge_score       DOUBLE,
                final_score           DOUBLE NOT NULL,
                failed                BOOLEAN NOT NULL,
                failure_reason        VARCHAR,
                judge_rule_disagreement BOOLEAN,
                latency_ms            DOUBLE,
                tokens_used           INTEGER,
                timestamp             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # ResultStorage.__init__ must detect and fix the stale schema
    storage = ResultStorage(db_path)

    with duckdb.connect(db_path) as conn:
        cols = {r[0] for r in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='test_results'"
        ).fetchall()}

    assert cols == _EXPECTED_TEST_RESULT_COLS, (
        f"Schema mismatch after migration: got {sorted(cols)}"
    )


def test_stale_run_summaries_schema_migrated_on_init(tmp_path):
    """When run_summaries has the old 10-column schema, ResultStorage rebuilds it."""
    db_path = str(tmp_path / "stale_summaries.duckdb")

    with duckdb.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE run_summaries (
                run_id                  VARCHAR NOT NULL,
                suite_name              VARCHAR NOT NULL,
                model                   VARCHAR NOT NULL,
                total_tests             INTEGER,
                failed_tests            INTEGER,
                failure_rate            DOUBLE,
                failure_by_category     VARCHAR,
                avg_latency_ms          DOUBLE,
                judge_disagreement_rate DOUBLE,
                created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (run_id, model)
            )
        """)

    storage = ResultStorage(db_path)

    with duckdb.connect(db_path) as conn:
        cols = {r[0] for r in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='run_summaries'"
        ).fetchall()}

    assert cols == _EXPECTED_RUN_SUMMARY_COLS, (
        f"run_summaries schema mismatch after migration: got {sorted(cols)}"
    )


def test_save_result_after_stale_schema_migration(tmp_path):
    """End-to-end: old DB → init → save_result → retrieve succeeds."""
    db_path = str(tmp_path / "stale_e2e.duckdb")

    with duckdb.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE test_results (
                id VARCHAR PRIMARY KEY, run_id VARCHAR NOT NULL,
                test_case_id VARCHAR NOT NULL, test_name VARCHAR NOT NULL,
                failure_category VARCHAR NOT NULL, perturbation_type VARCHAR NOT NULL,
                model VARCHAR NOT NULL, response TEXT,
                deterministic_score DOUBLE, llm_judge_score DOUBLE,
                final_score DOUBLE NOT NULL, failed BOOLEAN NOT NULL,
                failure_reason VARCHAR, judge_rule_disagreement BOOLEAN,
                latency_ms DOUBLE, tokens_used INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    storage = ResultStorage(db_path)
    storage.create_run("r-migrated", "suite", ["gpt-4o"])
    result = TestResult(
        run_id="r-migrated",
        test_case_id="tc1",
        test_name="test",
        failure_category="hallucination_overload",
        perturbation_type="distractor_injection",
        model="gpt-4o",
        response="some response",
        final_score=0.6,
        failed=False,
        latency_ms=200.0,
        disputed=True,
        prompt_tokens=30,
        completion_tokens=10,
        tokens_used=40,
        estimated_cost_usd=0.0002,
    )
    asyncio.run(storage.save_result(result))
    rows = storage.get_results_for_run("r-migrated")
    assert len(rows) == 1
    assert rows[0]["disputed"] is True
    assert rows[0]["estimated_cost_usd"] == pytest.approx(0.0002)
