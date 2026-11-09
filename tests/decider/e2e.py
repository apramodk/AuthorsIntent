"""Live End-to-End (E2E) decider tests against the TypeSafe Jev API."""

from pathlib import Path
import sys
from typing import Any
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.engines.jev_engine import JevEngine
from tests.decider.runner import build_decider_suite, run_cli


def build_e2e_suite(
    samples_by_set: dict[str, list[dict[str, Any]]],
    scoreboard: list[dict[str, Any]],
    token_totals: dict[str, int],
) -> unittest.TestSuite:
    return build_decider_suite(
        file_label="E2E",
        engine_factory=JevEngine,
        samples_by_set=samples_by_set,
        scoreboard=scoreboard,
        token_totals=token_totals,
    )


if __name__ == "__main__":
    sys.exit(run_cli(default_file="e2e"))
