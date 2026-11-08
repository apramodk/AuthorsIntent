"""Abstract base interface for decision engines."""

from abc import ABC, abstractmethod
from typing import Any


class DecisionEngine(ABC):
    """Abstract base class for System One decision engines (e.g., Jev, OpenJev)."""

    @abstractmethod
    def evaluate(self, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
        """Evaluate typed questions against the provided state."""
        raise NotImplementedError
