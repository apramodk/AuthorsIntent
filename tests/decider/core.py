"""Offline core unit tests for DeciderManager, Decider, and ConversationRouter.

Uses `logging` (`logger.debug` with `-v` / `--verbose`, `logger.info` for the
scoreboard summary) and registers each scenario in `intent_samples.json` and
`star_samples.json` as an independent `unittest` test method.
"""

from collections.abc import Callable
import json
import logging
from pathlib import Path
import sys
from typing import Any
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.engines.base import DecisionEngine
from src.harness.deciderManager import DeciderManager
from src.harness.router import ConversationRouter
from tests.decider.runner import (
     BOLD,
    CYAN,
    INTENT_SAMPLES_PATH,
    RESET,
    STAR_SAMPLES_PATH,
    format_intent_report,
    format_star_report,
    logger,
    run_cli,
)


class MockMultiDeciderEngine(DecisionEngine):
    """Deterministic engine returning mock Jev answers keyed by (question_set, segment)."""

    def __init__(
        self,
        intent_samples: list[dict[str, Any]],
        star_samples: list[dict[str, Any]],
    ) -> None:
        self._intent_by_segment = {
            item["state"]["segment"]: item["mock_answers"] for item in intent_samples
        }
        self._star_by_segment = {
            item["state"]["segment"]: item["mock_answers"] for item in star_samples
        }

    def evaluate(self, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
        segment = state.get("segment", "")
        if "is_inform" in questions:
            answers = self._intent_by_segment[segment]
        elif "has_situation" in questions:
            answers = self._star_by_segment[segment]
        else:
            raise KeyError(f"Unrecognized question set: {list(questions.keys())}")
        return {"model": "jev-mock", "answers": answers}


def build_core_suite(
    intent_samples: list[dict[str, Any]],
    star_samples: list[dict[str, Any]],
    scoreboard: list[dict[str, Any]],
) -> unittest.TestSuite:
    """Build the offline Core unittest.TestSuite with one test method per scenario."""

    class CoreDeciderTestCase(unittest.TestCase):
        engine: DecisionEngine
        manager: DeciderManager
        router: ConversationRouter

        @classmethod
        def setUpClass(cls) -> None:
            all_intent = json.loads(INTENT_SAMPLES_PATH.read_text(encoding="utf-8"))
            all_star = json.loads(STAR_SAMPLES_PATH.read_text(encoding="utf-8"))
            cls.engine = MockMultiDeciderEngine(all_intent, all_star)
            cls.manager = DeciderManager(engine=cls.engine)
            cls.router = ConversationRouter(manager=cls.manager)
            logger.debug(
                f"\n{BOLD}{CYAN}=== AuthorsIntent Core Decider Tests (Offline Mock) ==={RESET}"
            )

    def _make_intent_method(sample: dict[str, Any]) -> Callable[[CoreDeciderTestCase], None]:
        sample_id = sample["id"]
        state = sample["state"]
        expected = sample["expected"]

        def _test(self: CoreDeciderTestCase) -> None:
            result = self.manager.decide("intent", state)
            decision = self.router.route_from_intent(result)
            passed, report = format_intent_report(
                "CORE", sample_id, state["segment"], result, decision, expected, show_tokens=False
            )
            if passed:
                logger.debug(report)
            else:
                logger.error(report)

            scoreboard.append(
                {"file": "CORE", "set": "intent", "id": sample_id, "passed": passed}
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

        _test.__doc__ = f"[CORE][intent] {sample_id}"
        return _test

    def _make_star_method(sample: dict[str, Any]) -> Callable[[CoreDeciderTestCase], None]:
        sample_id = sample["id"]
        state = sample["state"]
        expected = sample["expected"]

        def _test(self: CoreDeciderTestCase) -> None:
            result = self.manager.decide("star", state)
            decision = self.router.route_from_star(result)
            passed, report = format_star_report(
                "CORE", sample_id, state["segment"], result, decision, expected, show_tokens=False
            )
            if passed:
                logger.debug(report)
            else:
                logger.error(report)

            scoreboard.append(
                {"file": "CORE", "set": "star", "id": sample_id, "passed": passed}
            )
            self.assertEqual(result.is_sufficient, expected["is_sufficient"], f"[{sample_id}] is_sufficient mismatch")
            self.assertEqual(result.output, expected["status"], f"[{sample_id}] status mismatch")
            self.assertEqual(
                result.missing_required,
                expected["missing_required"],
                f"[{sample_id}] missing_required mismatch",
            )
            self.assertEqual(decision.route, expected["route"], f"[{sample_id}] route mismatch")

        _test.__doc__ = f"[CORE][star] {sample_id}"
        return _test

    suite = unittest.TestSuite()
    for idx, sample in enumerate(intent_samples, start=1):
        method_name = f"test_core_01_intent_{idx:02d}_{sample['id']}"
        setattr(CoreDeciderTestCase, method_name, _make_intent_method(sample))
        suite.addTest(CoreDeciderTestCase(method_name))

    for idx, sample in enumerate(star_samples, start=1):
        method_name = f"test_core_02_star_{idx:02d}_{sample['id']}"
        setattr(CoreDeciderTestCase, method_name, _make_star_method(sample))
        suite.addTest(CoreDeciderTestCase(method_name))

    return suite


if __name__ == "__main__":
    sys.exit(run_cli(default_file="core"))
