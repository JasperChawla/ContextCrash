"""
Tests for core/config.py — YAML loading, retrieval knobs, depth levels, ordering.
"""
import textwrap
import pytest

from core.config import load_suite


def _write_yaml(tmp_path, content: str, name: str = "suite.yaml") -> str:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content))
    return str(p)


_BASE = """
    suite:
      name: "Base Suite"
    models:
      - gpt-4o-mini
    test_cases:
      - name: basic
        failure_category: instruction_loss
        perturbation: chunk_shuffle
        query: "What is revenue?"
        expected_behavior: "Cite sources"
        chunks:
          - "Revenue was $1B."
"""


def test_load_suite_creates_run_config(tmp_path):
    config = load_suite(_write_yaml(tmp_path, _BASE))
    assert config.suite_name == "Base Suite"
    assert config.models == ["gpt-4o-mini"]
    assert len(config.test_cases) == 1
    assert config.test_cases[0].name == "basic"


def test_load_suite_default_retrieval_knobs(tmp_path):
    config = load_suite(_write_yaml(tmp_path, _BASE))
    assert config.chunk_size == 512
    assert config.chunk_overlap == 50
    assert config.top_k == 5
    assert config.reranking_enabled is False
    assert config.chunk_ordering == "sequential"


def test_load_suite_custom_retrieval_knobs(tmp_path):
    yaml = _BASE + """
    retrieval:
      chunk_size: 256
      chunk_overlap: 25
      top_k: 3
      reranking_enabled: true
      chunk_ordering: reversed
    """
    config = load_suite(_write_yaml(tmp_path, yaml))
    assert config.chunk_size == 256
    assert config.chunk_overlap == 25
    assert config.top_k == 3
    assert config.reranking_enabled is True
    assert config.chunk_ordering == "reversed"


def test_load_suite_default_system_prompt(tmp_path):
    yaml = """
        suite:
          name: "Prompts"
        models:
          - gpt-4o
        defaults:
          system_prompt: "You are a helpful assistant."
        test_cases:
          - name: t
            failure_category: instruction_loss
            perturbation: chunk_shuffle
            query: "Q?"
            expected_behavior: "A"
            chunks:
              - "C1"
    """
    config = load_suite(_write_yaml(tmp_path, yaml))
    assert config.test_cases[0].system_prompt == "You are a helpful assistant."


def test_load_suite_test_level_chunk_ordering(tmp_path):
    yaml = """
        suite:
          name: "Ordering"
        models:
          - gpt-4o
        test_cases:
          - name: reversed_test
            failure_category: position_bias
            perturbation: chunk_shuffle
            chunk_ordering: reversed
            query: "Q?"
            expected_behavior: "A"
            chunks:
              - "C1"
              - "C2"
    """
    config = load_suite(_write_yaml(tmp_path, yaml))
    assert config.test_cases[0].chunk_ordering == "reversed"


def test_load_suite_context_depth_levels(tmp_path):
    yaml = """
        suite:
          name: "Depth"
        models:
          - gpt-4o
        test_cases:
          - name: depth_test
            failure_category: instruction_loss
            perturbation: chunk_shuffle
            context_depth_levels: [0.25, 0.5, 0.75, 1.0]
            query: "Q?"
            expected_behavior: "A"
            chunks:
              - "C1"
              - "C2"
              - "C3"
              - "C4"
    """
    config = load_suite(_write_yaml(tmp_path, yaml))
    assert config.test_cases[0].context_depth_levels == [0.25, 0.5, 0.75, 1.0]


def test_load_suite_validators_parsed(tmp_path):
    yaml = """
        suite:
          name: "Validators"
        models:
          - gpt-4o
        test_cases:
          - name: t
            failure_category: instruction_loss
            perturbation: chunk_shuffle
            query: "Q?"
            expected_behavior: "A"
            chunks:
              - "C1"
            validators:
              - type: contains_pattern
                pattern: "\\\\[\\\\d+\\\\]"
                weight: 1.0
    """
    config = load_suite(_write_yaml(tmp_path, yaml))
    assert len(config.test_cases[0].validators) == 1
    assert config.test_cases[0].validators[0].type == "contains_pattern"


def test_load_suite_history_contamination(tmp_path):
    yaml = """
        suite:
          name: "History"
        models:
          - gpt-4o
        test_cases:
          - name: hc_test
            failure_category: multi_turn_memory_decay
            perturbation: history_contamination
            perturbation_config:
              false_turns:
                - role: assistant
                  content: "Wrong answer: $800M."
              inject_at: 0
            history:
              - role: user
                content: "What is revenue?"
            query: "What did we discuss?"
            expected_behavior: "Use correct data"
            chunks:
              - "Revenue was $1B."
    """
    config = load_suite(_write_yaml(tmp_path, yaml))
    tc = config.test_cases[0]
    # Contamination injects an extra turn
    assert len(tc.conversation_history) >= 1


def test_load_suite_no_depth_levels_defaults_empty(tmp_path):
    config = load_suite(_write_yaml(tmp_path, _BASE))
    assert config.test_cases[0].context_depth_levels == []


def test_load_suite_no_chunk_ordering_defaults_none(tmp_path):
    config = load_suite(_write_yaml(tmp_path, _BASE))
    assert config.test_cases[0].chunk_ordering is None


def test_load_suite_failure_threshold(tmp_path):
    yaml = """
        suite:
          name: "S"
        models:
          - gpt-4o
        failure_threshold: 0.7
        test_cases:
          - name: t
            failure_category: instruction_loss
            perturbation: chunk_shuffle
            query: "Q?"
            expected_behavior: "A"
            chunks:
              - "C1"
    """
    config = load_suite(_write_yaml(tmp_path, yaml))
    assert config.failure_threshold == 0.7


def test_load_suite_db_path(tmp_path):
    yaml = """
        suite:
          name: "S"
        models:
          - gpt-4o
        db_path: "./custom/path.duckdb"
        test_cases:
          - name: t
            failure_category: instruction_loss
            perturbation: chunk_shuffle
            query: "Q?"
            expected_behavior: "A"
            chunks:
              - "C1"
    """
    config = load_suite(_write_yaml(tmp_path, yaml))
    assert config.db_path == "./custom/path.duckdb"
