"""Offline core unit tests for the AuthorsIntent intent evaluator and router.

Uses pre-recorded mock Jev probability distributions from
`tests/data/intent_samples.json` to deterministically verify schema loading,
macro intent truth-table derivation, companion Noul gating, and route selection.
"""

import json
from pathlib import Path
import sys
from typing import Any
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.engines.base import DecisionEngine
from src.harness.evaluator import IntentEvaluator, IntentEvaluation
from src.harness.router import IntentRouter, RouteDecision

SAMPLES_PATH = Path(__file__).resolve().parent / "data" / "intent_samples.json"

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"


def _color_prob(val: float) -> str:
    """Color a Noul probability by threshold band (>=0.7 green, 0.3-0.7 yellow, <0.3 dim)."""
    if val >= 0.7:
        return f"{GREEN}{BOLD}{val:.2f}{RESET}"
    if val >= 0.3:
        return f"{YELLOW}{val:.2f}{RESET}"
    return f"{DIM}{val:.2f}{RESET}"


def _color_match(got: Any, expected: Any) -> str:
    """Format a got vs expected comparison with green/red coloring."""
    if got == expected:
        return f"{GREEN}{BOLD}{got}{RESET} {DIM}(expected={expected}){RESET}"
    return f"{RED}{BOLD}{got}{RESET} {RED}(expected={expected}){RESET}"


def format_sample_report(
    sample_id: str,
    segment: str,
    evaluation: IntentEvaluation,
    decision: RouteDecision,
    expected: dict[str, Any],
) -> str:
    """Render a colorized summary block for a single test sample."""
    passed = (
        evaluation.macro_intent == expected["macro_intent"]
        and evaluation.micro_intent == expected["micro_intent"]
        and decision.route == expected["route"]
        and decision.requires_star_verification == expected["requires_star_verification"]
    )
    badge = f"{GREEN}{BOLD}[PASS]{RESET}" if passed else f"{RED}{BOLD}[FAIL]{RESET}"
    return (
        f"\n{badge} {CYAN}{BOLD}{sample_id}{RESET}\n"
        f"  {DIM}segment:{RESET} {segment}\n"
        f"  {DIM}nouls:{RESET}   is_inform={_color_prob(evaluation.is_inform_prob)}, "
        f"is_persuade={_color_prob(evaluation.is_persuade_prob)}, "
        f"has_micro={_color_prob(evaluation.has_micro_intent_prob)}\n"
        f"  {DIM}macro:{RESET}   {_color_match(evaluation.macro_intent, expected['macro_intent'])}\n"
        f"  {DIM}micro:{RESET}   {_color_match(evaluation.micro_intent, expected['micro_intent'])}\n"
        f"  {DIM}route:{RESET}   {_color_match(decision.route, expected['route'])} "
        f"{MAGENTA}[STAR={decision.requires_star_verification}]{RESET}"
    )


class MockDecisionEngine(DecisionEngine):
    """Deterministic engine returning pre-recorded Jev answers keyed by segment."""

    def __init__(self, samples: list[dict[str, Any]]) -> None:
        self._by_segment: dict[str, dict[str, Any]] = {
            item["state"]["segment"]: item["mock_answers"] for item in samples
        }

    def evaluate(self, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
        segment = state.get("segment", "")
        if segment not in self._by_segment:
            raise KeyError(f"No mock answers registered for segment: {segment!r}")
        answers = self._by_segment[segment]
        for q_id in questions:
            if q_id not in answers:
                raise AssertionError(f"Mock sample missing answer for schema question {q_id!r}")
        return {"model": "jev-mock", "answers": answers}


class IntentCoreTest(unittest.TestCase):
    """Validates core truth-table derivation and routing over mock Jev distributions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.samples: list[dict[str, Any]] = json.loads(
            SAMPLES_PATH.read_text(encoding="utf-8")
        )
        cls.engine = MockDecisionEngine(cls.samples)
        cls.evaluator = IntentEvaluator(cls.engine)
        cls.router = IntentRouter()

    def test_core_intent_routing(self) -> None:
        print(f"\n{BOLD}{CYAN}=== AuthorsIntent Core Routing Tests (Offline Mock) ==={RESET}")
        for sample in self.samples:
            sample_id = sample["id"]
            state = sample["state"]
            expected = sample["expected"]

            with self.subTest(sample_id=sample_id):
                evaluation = self.evaluator.evaluate_segment(
                    segment=state["segment"],
                    conversation_context=state.get("conversation_context"),
                )
                decision = self.router.route_intent(evaluation)
                print(
                    format_sample_report(
                        sample_id, state["segment"], evaluation, decision, expected
                    )
                )

                self.assertEqual(
                    evaluation.macro_intent,
                    expected["macro_intent"],
                    f"[{sample_id}] macro_intent mismatch",
                )
                self.assertEqual(
                    evaluation.micro_intent,
                    expected["micro_intent"],
                    f"[{sample_id}] micro_intent mismatch",
                )
                self.assertEqual(
                    decision.route,
                    expected["route"],
                    f"[{sample_id}] route mismatch",
                )
                self.assertEqual(
                    decision.requires_star_verification,
                    expected["requires_star_verification"],
                    f"[{sample_id}] requires_star_verification mismatch",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
