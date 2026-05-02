from abc import ABC, abstractmethod
from typing import Optional, Tuple

from core.models import TestCase


class BaseEvaluator(ABC):
    @abstractmethod
    def evaluate(self, test_case: TestCase, response: str) -> Tuple[float, Optional[str]]:
        """Returns (score 0.0-1.0, failure_reason or None)."""
        ...
