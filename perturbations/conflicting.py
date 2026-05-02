import random
import re
from typing import Any, Dict, List

from perturbations.base import BasePerturbation


class ConflictingEvidencePerturbation(BasePerturbation):
    """Injects a chunk that directly contradicts an existing chunk.

    Tests whether the model detects and flags contradictions or silently
    picks one side (typically the last occurrence it sees).
    """

    @property
    def name(self) -> str:
        return "conflicting_evidence"

    def apply(self, chunks: List[str], config: Dict[str, Any]) -> List[str]:
        conflict_chunk = config.get("conflict_chunk")
        target_index = config.get("target_index", 0)
        seed = config.get("seed", 42)
        rng = random.Random(seed)

        result = chunks[:]

        if conflict_chunk:
            # User explicitly provided the conflicting chunk
            pos = config.get("insert_at", len(result))
            result.insert(pos, conflict_chunk)
        elif result:
            # Auto-generate a conflict by negating numbers/assertions in target chunk
            original = result[min(target_index, len(result) - 1)]
            conflicting = self._negate_chunk(original, rng)
            insert_pos = rng.randint(0, len(result))
            result.insert(insert_pos, conflicting)

        return result

    def _negate_chunk(self, text: str, rng: random.Random) -> str:
        """Simple negation: flip numbers, add 'NOT', invert directional claims."""
        negated = text

        # Flip percentage numbers (e.g., 15% -> 85%, 30% -> 70%)
        def flip_percent(m):
            val = int(m.group(1))
            return f"{100 - val}%"

        negated = re.sub(r"(\d+)%", flip_percent, negated)

        # Flip "increased" <-> "decreased", "grew" <-> "fell"
        flips = [
            ("increased", "decreased"),
            ("decreased", "increased"),
            ("grew", "fell"),
            ("fell", "grew"),
            ("positive", "negative"),
            ("negative", "positive"),
            ("higher", "lower"),
            ("lower", "higher"),
        ]
        for a, b in flips:
            if a in negated.lower():
                negated = re.sub(a, b, negated, flags=re.IGNORECASE)
                break

        # Add a marker so evaluators can detect this is a planted conflict
        return f"[CONFLICTING DATA] {negated}"
