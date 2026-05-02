import re
from typing import Any, Dict, List

from perturbations.base import BasePerturbation

# Word-level synonym substitutions for deterministic paraphrasing.
# Real-world alternative: call an LLM to paraphrase - but that adds latency
# and cost to the setup phase, and determinism matters for reproducibility.
_SYNONYMS = {
    "revenue": "income",
    "increase": "rise",
    "decrease": "drop",
    "report": "document",
    "company": "organization",
    "product": "offering",
    "customer": "client",
    "significant": "notable",
    "approximately": "roughly",
    "implement": "deploy",
    "analyze": "examine",
    "provide": "offer",
    "require": "need",
    "improve": "enhance",
    "reduce": "lower",
}


class ParaphraseEvidencePerturbation(BasePerturbation):
    """Rewrites key chunks using synonyms/restructuring while preserving meaning.

    Exposes brittleness in exact-match retrieval and tests whether the model
    can reason over paraphrased evidence vs. verbatim quotes.
    """

    @property
    def name(self) -> str:
        return "paraphrase_evidence"

    def apply(self, chunks: List[str], config: Dict[str, Any]) -> List[str]:
        target_indices = config.get("target_indices", list(range(len(chunks))))
        custom_synonyms = config.get("synonyms", {})

        synonyms = {**_SYNONYMS, **custom_synonyms}
        result = []

        for i, chunk in enumerate(chunks):
            if i in target_indices:
                result.append(self._paraphrase(chunk, synonyms))
            else:
                result.append(chunk)

        return result

    def _paraphrase(self, text: str, synonyms: Dict[str, str]) -> str:
        result = text
        for original, replacement in synonyms.items():
            # Word-boundary match to avoid partial replacements like "increase" -> "rise" in "increases"
            result = re.sub(
                rf"\b{original}\b",
                replacement,
                result,
                flags=re.IGNORECASE,
            )
        return result
