"""TypeSafe Jev decision engine implementation backed by `typesafe-sdk`."""

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from typesafe_sdk import SystemOneResponse, TypeSafeClient

from .base import DecisionEngine


class JevEngine(DecisionEngine):
    """DecisionEngine backed by TypeSafe's official `typesafe-sdk` client."""

    DEFAULT_MODEL = "jev-latest"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        base_url: str | None = None,
        timeout: float = 30.0,
        dotenv_path: Path | None = None,
    ) -> None:
        env_file = dotenv_path or (Path(__file__).resolve().parents[2] / ".env")
        load_dotenv(dotenv_path=env_file, override=False)

        resolved_key = (
            api_key
            or os.environ.get("JEV_KEY")
            or os.environ.get("TYPESAFE_API_KEY")
        )
        if not resolved_key:
            raise ValueError(
                "Missing API key: set JEV_KEY (or TYPESAFE_API_KEY) in environment or .env"
            )

        self.model = model
        self.client = TypeSafeClient(
            api_key=resolved_key,
            model=model,
            base_url=base_url,
            timeout=timeout,
        )

    def evaluate_typed(
        self, state: dict[str, Any], questions: dict[str, Any]
    ) -> SystemOneResponse:
        """Evaluate typed questions via `TypeSafeClient.system_one` and return `SystemOneResponse`."""
        return self.client.system_one(
            state=state,
            questions=questions,
            model=self.model,
        )

    def evaluate(self, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
        """Evaluate typed questions against the provided state and return a plain dictionary."""
        response = self.evaluate_typed(state=state, questions=questions)
        return response.model_dump()

    def close(self) -> None:
        """Close the underlying TypeSafe HTTP client."""
        self.client.close()
