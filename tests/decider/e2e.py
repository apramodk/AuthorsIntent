"""Live End-to-End (E2E) tests for DeciderManager, Decider, and ConversationRouter.

Uses `logging` (`logger.debug` with `-v` / `--verbose`, `logger.info` for the
scoreboard and token usage summary) and registers each scenario in
`intent_samples.json` and `star_samples.json` as an independent `unittest`
test method against the live TypeSafe Jev API.
"""

from collections.abc import Callable
from pathlib import Path
import sys
from typing import Any
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.engines.jev_engine import JevEngine
from src.harness.deciderManager import DeciderManager
from src.harness.router import ConversationRouter
from tests.decider.runner import (
    BOLD,
    CYAN,
    RESET,
    format_intent_report,
    format_star_report,
    logger,
    run_cli,
)


def build_e2e_suite(
    intent_samples: list[dict[str, Any]],
    star_samples: list[dict[str, Any]],
    scoreboard: list[dict[str, Any]],
    token_totals: dict[str, int],
) -> unittest.TestSuite:
    """Build the live Jev E2E unittest.TestSuite with one test method per scenario."""

    class E2EDeciderTestCase(unittest.TestCase):
        engine: JevEngine
        manager: DeciderManager
        router: ConversationRouter

        @classmethod
        def setUpClass(cls) -> None:
            cls.engine = JevEngine()
            cls.manager = DeciderManager(engine=cls.engine)
            cls.router = ConversationRouter(manager=cls.manager)
            logger.debug(
                f"\n{BOLD}{CYAN}=== AuthorsIntent Live E2E Decider Tests (Model: {cls.engine.model}) ==={RESET}"
            )

        @classmethod
        def tearDownClass(cls) -> None:
            cls.engine.close()

    def _make_intent_method(sample: dict[str, Any]) -> Callable[[E2EDeciderTestCase], None]:
        sample_id = sample["id"]
        state = sample["state"]
        expected = sample["expected"]

        def _test(self: E2EDeciderTestCase) -> None:
            result = self.manager.decide("intent", state)
            decision = self.router.route_from_intent(result)
            token_totals["input"] += result.input_tokens or 0
            token_totals["output"] += result.output_tokens or 0
            token_totals["scenarios"] += 1

            passed, report = format_intent_report(
                "E2E", sample_id, state["segment"], result, decision, expected, show_tokens=True
            )
            if passed:
                logger.debug(report)
            else:
                logger.error(report)

            scoreboard.append(
                {"file": "E2E", "set": "intent", "id": sample_id, "passed": passed}
            )
            self.assertEqual(result.output, expected["macro_intent"], f"[{sample_id}] macro_intent mismatch")
            self.assertEqual(
                result.choices.get("micro_intent"),
                expected["micro_intent"],
                f"[{sample_id}] micro_intent mismatch",
            )
            self.assertEqual(decision.route, expected["route"], f"[{sample_id}] route mismatch")
            self.assertEqual(
                decision.requires_star_verification,
                expected["requires_star_verification"],
                f"[{sample_id}] requires_star_verification mismatch",
            )

        _test.__doc__ = f"[E2E][intent] {sample_id}"
        return _test

    def _make_star_method(sample: dict[str, Any]) -> Callable[[E2EDeciderTestCase], None]:
        sample_id = sample["id"]
        state = sample["state"]
        expected = sample["expected"]

        def _test(self: E2EDeciderTestCase) -> None:
            result = self.manager.decide("star", state)
            decision = self.router.route_from_star(result)
            token_totals["input"] += result.input_tokens or 0
            token_totals["output"] += result.output_tokens or 0
            token_totals["scenarios"] += 1

            passed, report = format_star_report(
                "E2E", sample_id, state["segment"], result, decision, expected, show_tokens=True
            )
            if passed:
                logger.debug(report)
            else:
                logger.error(report)

            scoreboard.append(
                {"file": "E2E", "set": "star", "id": sample_id, "passed": passed}
            )
            self.assertEqual(result.is_sufficient, expected["is_sufficient"], f"[{sample_id}] is_sufficient mismatch")
            self.assertEqual(result.output, expected["status"], f"[{sample_id}] status mismatch")
            self.assertEqual(
                result.missing_required,
                expected["missing_required"],
                f"[{sample_id}] missing_required mismatch",
            )
            self.assertEqual(decision.route, expected["route"], f"[{sample_id}] route mismatch")

        _test.__doc__ = f"[E2E][star] {sample_id}"
        return _test

    suite = unittest.TestSuite()
    for idx, sample in enumerate(intent_samples, start=1):
        method_name = f"test_e2e_01_intent_{idx:02d}_{sample['id']}"
        setattr(E2EDeciderTestCase, method_name, _make_intent_method(sample))
        suite.addTest(E2EDeciderTestCase(method_name))

    for idx, sample in enumerate(star_samples, start=1):
        method_name = f"test_e2e_02_star_{idx:02d}_{sample['id']}"
        setattr(E2EDeciderTestCase, method_name, _make_star_method(sample))
        suite.addTest(E2EDeciderTestCase(method_name))

    return suite


if __name__ == "__main__":
    sys.exit(run_cli(default_file="e2e"))
