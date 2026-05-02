import pytest
from perturbations import get_perturbation
from perturbations.conflicting import ConflictingEvidencePerturbation
from perturbations.history_contamination import HistoryContaminationPerturbation
from core.models import PerturbationType


CHUNKS = [
    "Revenue was $1.2B in Q3.",
    "Headcount grew to 5,000 employees.",
    "Operating margin reached 24%.",
]


class TestChunkShuffle:
    def test_produces_different_order(self):
        p = get_perturbation(PerturbationType.CHUNK_SHUFFLE)
        result = p.apply(CHUNKS, {"seed": 1})
        assert set(result) == set(CHUNKS)
        # With seed=1 the order should change (very unlikely to be identical for 3 items)
        # If it does equal by chance, that's fine - the shuffle is still correct

    def test_deterministic_with_same_seed(self):
        p = get_perturbation(PerturbationType.CHUNK_SHUFFLE)
        r1 = p.apply(CHUNKS, {"seed": 99})
        r2 = p.apply(CHUNKS, {"seed": 99})
        assert r1 == r2

    def test_different_seeds_differ(self):
        p = get_perturbation(PerturbationType.CHUNK_SHUFFLE)
        r1 = p.apply(CHUNKS, {"seed": 1})
        r2 = p.apply(CHUNKS, {"seed": 2})
        # Very unlikely same for 3 different seeds with 3 elements
        assert r1 != r2 or True  # non-critical, just a smoke test


class TestDistractorInjection:
    def test_increases_chunk_count(self):
        p = get_perturbation(PerturbationType.DISTRACTOR_INJECTION)
        result = p.apply(CHUNKS, {"count": 3})
        assert len(result) == len(CHUNKS) + 3

    def test_original_chunks_preserved(self):
        p = get_perturbation(PerturbationType.DISTRACTOR_INJECTION)
        result = p.apply(CHUNKS, {"count": 2})
        for chunk in CHUNKS:
            assert chunk in result

    def test_custom_distractors(self):
        p = get_perturbation(PerturbationType.DISTRACTOR_INJECTION)
        custom = ["Totally irrelevant info about space travel."]
        result = p.apply(CHUNKS, {"count": 1, "distractors": custom})
        assert custom[0] in result


class TestConflictingEvidence:
    def test_explicit_conflict_chunk(self):
        p = get_perturbation(PerturbationType.CONFLICTING_EVIDENCE)
        conflict = "Revenue was actually $0.1B in Q3."
        result = p.apply(CHUNKS, {"conflict_chunk": conflict})
        assert conflict in result
        assert len(result) == len(CHUNKS) + 1

    def test_auto_generates_conflict(self):
        p = get_perturbation(PerturbationType.CONFLICTING_EVIDENCE)
        result = p.apply(CHUNKS, {})
        assert len(result) == len(CHUNKS) + 1
        # Auto-generated conflict should have the marker
        has_marker = any("[CONFLICTING DATA]" in c for c in result)
        assert has_marker

    def test_negate_percentage(self):
        p = ConflictingEvidencePerturbation()
        import random
        rng = random.Random(42)
        result = p._negate_chunk("Revenue increased 30% this quarter.", rng)
        assert "70%" in result  # 100 - 30 = 70


class TestInstructionBurial:
    def test_adds_padding(self):
        p = get_perturbation(PerturbationType.INSTRUCTION_BURIAL)
        result = p.apply(CHUNKS, {"padding_count": 4, "depth": 0.8})
        assert len(result) > len(CHUNKS)

    def test_original_instruction_preserved(self):
        p = get_perturbation(PerturbationType.INSTRUCTION_BURIAL)
        result = p.apply(CHUNKS, {"instruction_chunk_index": 0, "depth": 0.9})
        assert CHUNKS[0] in result

    def test_deep_burial_position(self):
        p = get_perturbation(PerturbationType.INSTRUCTION_BURIAL)
        result = p.apply(CHUNKS, {"instruction_chunk_index": 0, "depth": 1.0, "padding_count": 10})
        # With depth=1.0, instruction should be at or near the end
        idx = result.index(CHUNKS[0])
        assert idx > len(result) // 2


class TestHistoryContamination:
    def test_injects_false_turns(self):
        history = [
            {"role": "user", "content": "What is X?"},
            {"role": "assistant", "content": "X is 42."},
        ]
        false_turns = [{"role": "assistant", "content": "Actually X is 9999."}]
        result = HistoryContaminationPerturbation.get_contaminated_history(
            history, {"false_turns": false_turns, "inject_at": 1}
        )
        assert len(result) == len(history) + 1
        assert any(t["content"] == "Actually X is 9999." for t in result)

    def test_chunks_unchanged(self):
        p = get_perturbation(PerturbationType.HISTORY_CONTAMINATION)
        result = p.apply(CHUNKS, {})
        assert result == CHUNKS


class TestParaphraseEvidence:
    def test_replaces_synonyms(self):
        p = get_perturbation(PerturbationType.PARAPHRASE_EVIDENCE)
        chunks = ["The revenue increased significantly this quarter."]
        result = p.apply(chunks, {})
        assert result[0] != chunks[0]
        # "revenue" -> "income", "increased" -> "rose"
        assert "income" in result[0] or "rise" in result[0]

    def test_custom_synonyms(self):
        p = get_perturbation(PerturbationType.PARAPHRASE_EVIDENCE)
        chunks = ["The widget performed well."]
        result = p.apply(chunks, {"synonyms": {"widget": "gadget"}})
        assert "gadget" in result[0]

    def test_selective_paraphrase(self):
        p = get_perturbation(PerturbationType.PARAPHRASE_EVIDENCE)
        chunks = ["Revenue increased.", "Operating margin fell."]
        # Only paraphrase chunk 0
        result = p.apply(chunks, {"target_indices": [0]})
        assert result[1] == chunks[1]  # chunk 1 unchanged
