"""Test suite for the AuthorsIntent intent evaluator and router.

Runs offline against `tests/data/intent_samples.json` by default using a mock
DecisionEngine, and supports `--live` to evaluate the exact same samples against
the live TypeSafe Jev API using `JEV_KEY` from `.env`.
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Any
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.engines.base import DecisionEngine
from src.engines.jev_engine import JevEngine
from src.harness.evaluator import IntentEvaluator
from src.harness.router import IntentRouter

SAMPLES_PATH = Path(__file__).resolve().parent / "data" / "intent_samples.json"


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
        # Ensure all schema questions exist in mock answers
        answers = self._by_segment[segment]
        for q_id in questions:
            if q_id not in answers:
                raise AssertionError(f"Mock sample missing answer for schema question {q_id!r}")
        return {"model": "jev-mock", "answers": answers}


class IntentRouterTest(unittest.TestCase):
    """Validates schema loading, macro intent derivation, companion Noul gating, and routing."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.samples: list[dict[str, Any]] = json.loads(
            SAMPLES_PATH.read_text(encoding="utf-8")
        )
        cls.engine = MockDecisionEngine(cls.samples)
        cls.evaluator = IntentEvaluator(cls.engine)
        cls.router = IntentRouter()

    def test_all_intent_samples(self) -> None:
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


def run_live_probe() -> int:
    """Send the sample states in tests/data/intent_samples.json to the live Jev API."""
    samples: list[dict[str, Any]] = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    engine = JevEngine()
    evaluator = IntentEvaluator(engine)
    router = IntentRouter()

    passed = 0
    print(f"Running {len(samples)} samples against live Jev ({engine.model})...\n")
    for sample in samples:
        sample_id = sample["id"]
        state = sample["state"]
        expected = sample["expected"]

        evaluation = evaluator.evaluate_segment(
            segment=state["segment"],
            conversation_context=state.get("conversation_context"),
        )
        decision = router.route_intent(evaluation)

        macro_ok = evaluation.macro_intent == expected["macro_intent"]
        micro_ok = evaluation.micro_intent == expected["micro_intent"]
        route_ok = decision.route == expected["route"]
        all_ok = macro_ok and micro_ok and route_ok
        if all_ok:
            passed += 1

        status = "PASS" if all_ok else "DIFF"
        print(
            f"[{status}] {sample_id}\n"
            f"  segment: {state['segment']}\n"
            f"  nouls:   is_inform={evaluation.is_inform_prob:.2f}, "
            f"is_persuade={evaluation.is_persuade_prob:.2f}, "
            f"has_micro={evaluation.has_micro_intent_prob:.2f}\n"
            f"  macro:   got={evaluation.macro_intent} (expected={expected['macro_intent']})\n"
            f"  micro:   got={evaluation.micro_intent} (expected={expected['micro_intent']})\n"
            f"  route:   got={decision.route} (expected={expected['route']})\n"
        )

    print(f"Summary: {passed}/{len(samples)} matched expected labels.")
    return 0 if passed == len(samples) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AuthorsIntent routing tests.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Send test samples to the live TypeSafe Jev API using JEV_KEY from .env",
    )
    args, remaining = parser.parse_known_args()
    if args.live:
        sys.exit(run_live_probe())
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
