import os
import tempfile
import pytest

from core.models import FailureCategory, PerturbationType, TestCase


@pytest.fixture
def sample_chunks():
    return [
        "Q3 2024 revenue was $1.2 billion, representing 15% year-over-year growth.",
        "The company expanded into three new markets: Brazil, South Korea, and Poland.",
        "CEO Jane Smith stated: 'Our cost structure remains competitive and lean.'",
        "Operating margin improved to 24%, up from 19% in Q3 2023.",
    ]


@pytest.fixture
def sample_test_case(sample_chunks):
    return TestCase(
        name="test_instruction_loss",
        failure_category=FailureCategory.INSTRUCTION_LOSS,
        perturbation_type=PerturbationType.CHUNK_SHUFFLE,
        system_prompt="You are a helpful assistant. Always cite sources using [1], [2], etc.",
        chunks=sample_chunks,
        user_query="What was the revenue in Q3 2024?",
        expected_behavior="Response must include citation markers like [1] or [2].",
    )


@pytest.fixture
def temp_db(tmp_path):
    db_path = str(tmp_path / "test_results.duckdb")
    return db_path
