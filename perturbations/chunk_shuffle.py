import random
from typing import Any, Dict, List

from perturbations.base import BasePerturbation


class ChunkShufflePerturbation(BasePerturbation):
    """Randomizes chunk order to expose position bias.

    Models often over-index on the first/last chunk in context. Shuffling
    reveals whether the model is doing semantic retrieval or just position
    lookup.
    """

    @property
    def name(self) -> str:
        return "chunk_shuffle"

    def apply(self, chunks: List[str], config: Dict[str, Any]) -> List[str]:
        seed = config.get("seed", 42)
        rng = random.Random(seed)
        shuffled = chunks[:]
        rng.shuffle(shuffled)
        return shuffled
