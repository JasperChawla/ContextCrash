from typing import Any, Dict, List

from perturbations.base import BasePerturbation


class HistoryContaminationPerturbation(BasePerturbation):
    """Injects false or misleading turns into conversation history.

    Tests whether the model correctly attributes information to current context
    vs. contaminated history. Critical for multi-turn RAG where history is
    appended verbatim and users can plant false premises.
    """

    @property
    def name(self) -> str:
        return "history_contamination"

    def apply(self, chunks: List[str], config: Dict[str, Any]) -> List[str]:
        # This perturbation primarily modifies conversation_history, not chunks.
        # The config carries the contamination payload; the runner checks for it.
        # We still return chunks unmodified - history is injected in runner.py.
        return chunks

    @staticmethod
    def get_contaminated_history(
        original_history: List[Dict],
        config: Dict[str, Any],
    ) -> List[Dict]:
        """Returns a history list with injected false assistant turns."""
        false_turns = config.get("false_turns", [])
        inject_at = config.get("inject_at", 0)

        result = original_history[:]
        for i, turn in enumerate(false_turns):
            result.insert(inject_at + i, turn)

        return result
