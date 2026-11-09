"""Offline core unit tests using a deterministic MockDecisionClient."""

import json
from pathlib import Path
import sys
from typing import Any
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.clients import DecisionClient
from tests.runner import build_decider_suite, discover_sample_sets, run_cli


class MockDecisionClient(DecisionClient):
    """Deterministic client returning mock answers keyed by serialized state across all sample sets."""

    def __init__(self, all_samples: dict[str, list[dict[str, Any]]]) -> None:
        self._by_state_key: dict[str, dict[str, Any]] = {}
        for samples in all_samples.values():
            for item in samples:
                key = json.dumps(item["state"], sort_keys=True)
                self._by_state_key[key] = item["mock_answers"]

    def evaluate(self, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
        key = json.dumps(state, sort_keys=True)
        return {"model": "jev-mock", "answers": self._by_state_key[key]}


def build_core_suite(
    samples_by_set: dict[str, list[dict[str, Any]]],
    scoreboard: list[dict[str, Any]],
) -> unittest.TestSuite:
    all_samples = discover_sample_sets()
    return build_decider_suite(
        file_label="CORE",
        client_factory=lambda: MockDecisionClient(all_samples),
        samples_by_set=samples_by_set,
        scoreboard=scoreboard,
        token_totals=None,
    )


if __name__ == "__main__":
    sys.exit(run_cli(default_file="core"))
