import random
from typing import Any, Dict, List

from perturbations.base import BasePerturbation

# Distractors are plausible-looking but irrelevant chunks.
# Using domain-generic text so they're model-agnostic.
_DISTRACTOR_POOL = [
    "The quarterly earnings call is scheduled for next Tuesday at 9 AM EST.",
    "Our data retention policy requires all logs to be purged after 90 days.",
    "The office will be closed on December 25th and January 1st for the holidays.",
    "Please submit expense reports by the 15th of each month for timely reimbursement.",
    "The engineering team completed the migration to the new CI/CD pipeline last week.",
    "According to our SLA, response times must not exceed 200ms at p99.",
    "The board approved a 10% increase in the R&D budget for the upcoming fiscal year.",
    "All new hires must complete the security training module within their first week.",
    "The latest performance review cycle begins in March and ends in April.",
    "Version 2.4.1 of the internal SDK was released with several bug fixes.",
]


class DistractorInjectionPerturbation(BasePerturbation):
    """Injects irrelevant chunks at random positions to test retrieval focus.

    The model should answer from the relevant chunks and ignore noise.
    High distractor counts stress-test attention mechanisms.
    """

    @property
    def name(self) -> str:
        return "distractor_injection"

    def apply(self, chunks: List[str], config: Dict[str, Any]) -> List[str]:
        count = config.get("count", 2)
        seed = config.get("seed", 42)
        custom_distractors = config.get("distractors", [])

        rng = random.Random(seed)
        pool = custom_distractors if custom_distractors else _DISTRACTOR_POOL
        distractors = rng.sample(pool, min(count, len(pool)))

        result = chunks[:]
        for d in distractors:
            pos = rng.randint(0, len(result))
            result.insert(pos, d)

        return result
