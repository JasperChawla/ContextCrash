from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BasePerturbation(ABC):
    """All perturbations transform a list of context chunks + optional metadata.

    They're applied at load time (config.py), not during the test run, so the
    perturbed inputs are deterministic and reproducible given the same YAML.
    """

    @abstractmethod
    def apply(self, chunks: List[str], config: Dict[str, Any]) -> List[str]:
        """Return perturbed version of the chunk list."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...
