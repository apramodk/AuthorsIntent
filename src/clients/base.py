"""Abstract base interface for System One decision model clients."""

from abc import ABC, abstractmethod
from typing import Any


class DecisionClient(ABC):
    """Abstract base class for System One decision clients (e.g., Jev, OpenJev)."""

    @abstractmethod
    def evaluate(self, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
        """Evaluate typed questions against the provided state."""
        raise NotImplementedError
