"""TypeSafe Jev decision engine implementation."""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .base import DecisionEngine


def _load_dotenv(dotenv_path: Path | None = None) -> None:
    """Load simple KEY=VALUE pairs from a .env file if present."""
    path = dotenv_path or Path(__file__).resolve().parents[2] / ".env"
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


class JevEngine(DecisionEngine):
    """DecisionEngine backed by TypeSafe's Jev model."""

    DEFAULT_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
    DEFAULT_MODEL = "jev-latest"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 30.0,
    ) -> None:
        _load_dotenv()
        self.api_key = api_key or os.environ.get("JEV_KEY") or os.environ.get("TYPESAFE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Missing API key: set JEV_KEY (or TYPESAFE_API_KEY) in environment or .env"
            )
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout

    def build_payload(self, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
        """Construct the exact TypeSafe System One request payload."""
        return {
            "model": self.model,
            "state": state,
            "questions": questions,
        }

    def evaluate(self, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
        """Evaluate typed questions against the provided state using Jev."""
        payload = self.build_payload(state, questions)
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"TypeSafe Jev API error ({exc.code}): {error_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"TypeSafe Jev network error: {exc.reason}") from exc
