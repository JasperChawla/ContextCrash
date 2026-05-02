from typing import Any, Dict, List

from perturbations.base import BasePerturbation

# Generic padding text to bury instructions deep in context.
# Semantically neutral to avoid confusing the model about the topic.
_PADDING_TEMPLATE = (
    "The following background information may be relevant to your analysis. "
    "Please review all provided context carefully before formulating your response. "
    "Context section {n}: This section contains supporting documentation "
    "that provides additional detail on the subject matter under discussion."
)


class InstructionBurialPerturbation(BasePerturbation):
    """Pushes the key instruction chunk deep into the context window.

    LLMs have documented recency and primacy biases - instructions buried
    at 70-90% depth are frequently ignored. This perturbation quantifies that.
    """

    @property
    def name(self) -> str:
        return "instruction_burial"

    def apply(self, chunks: List[str], config: Dict[str, Any]) -> List[str]:
        depth = config.get("depth", 0.8)  # 0.0 = beginning, 1.0 = end
        padding_count = config.get("padding_count", 5)
        instruction_index = config.get("instruction_chunk_index", 0)

        if not chunks:
            return chunks

        # Extract the chunk that contains the key instruction
        instruction_chunk = chunks[instruction_index]
        remaining = [c for i, c in enumerate(chunks) if i != instruction_index]

        # Build padding to inflate context size
        padding = [
            _PADDING_TEMPLATE.format(n=i + 1) for i in range(padding_count)
        ]
        all_content = remaining + padding

        # Insert instruction at the target depth
        insert_at = max(0, int(len(all_content) * depth))
        all_content.insert(insert_at, instruction_chunk)

        return all_content
