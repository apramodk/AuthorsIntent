"""Unified test runner, generic report formatter, and suite builder for AuthorsIntent deciders."""

import argparse
from collections.abc import Callable
import json
import logging
from pathlib import Path
import sys
from typing import Any
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import ConversationRouter
from src.clients import DecisionClient
from src.deciders import DecisionResult

DATA_DIR = Path(__file__).resolve().parent / "data"
logger = logging.getLogger("authors_intent.tests")

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"


def configure_logging(verbose: bool) -> None:
    """Configure test logger level (`DEBUG` when `-v` is passed, `INFO` otherwise)."""
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.propagate = False


def _color_prob(val: float) -> str:
    if val >= 0.7:
        return f"{GREEN}{BOLD}{val:.2f}{RESET}"
    if val >= 0.3:
        return f"{YELLOW}{val:.2f}{RESET}"
    return f"{DIM}{val:.2f}{RESET}"


def _color_match(got: Any, expected: Any) -> str:
    if got == expected:
        return f"{GREEN}{BOLD}{got}{RESET} {DIM}(expected={expected}){RESET}"
    return f"{RED}{BOLD}{got} (expected={expected}) <-- MISMATCH{RESET}"


def _summarize_state(state: dict[str, Any]) -> str:
    if "segment" in state:
        return str(state["segment"])
    if "candidate_message" in state:
        cand = state["candidate_message"]
        return f"[{cand.get('role', 'user')}] {cand.get('content', '')}"
    return json.dumps(state, ensure_ascii=False)


def format_decision_report(
    file_label: str,
    decider_name: str,
    sample_id: str,
    state: dict[str, Any],
    result: DecisionResult,
    expected: dict[str, Any],
    show_tokens: bool = False,
) -> tuple[bool, str]:
    """Generic report formatter for any Decider schema and DecisionResult."""
    passed = result.output == expected["output"]
    for choice_key, exp_choice in expected.get("choices", {}).items():
        passed = passed and (result.choices.get(choice_key) == exp_choice)
    if "is_sufficient" in expected:
        passed = passed and (result.is_sufficient == expected["is_sufficient"])
    if "missing_required" in expected:
        passed = passed and (result.missing_required == expected["missing_required"])

    badge = f"{GREEN}{BOLD}[PASS]{RESET}" if passed else f"{RED}{BOLD}[FAIL]{RESET}"
    nouls_str = ", ".join(f"{k}={_color_prob(v)}" for k, v in result.probabilities.items())

    lines = [
        f"\n{badge} {MAGENTA}[{file_label}]{RESET} {CYAN}{BOLD}[{decider_name}] {sample_id}{RESET}",
        f"  {DIM}input:{RESET}    {_summarize_state(state)}",
        f"  {DIM}nouls:{RESET}    {nouls_str}",
        f"  {DIM}output:{RESET}   {_color_match(result.output, expected['output'])}",
    ]

    for choice_key, exp_choice in expected.get("choices", {}).items():
        got_choice = result.choices.get(choice_key)
        lines.append(f"  {DIM}{choice_key}:{RESET} {_color_match(got_choice, exp_choice)}")

    if "is_sufficient" in expected:
        lines.append(
            f"  {DIM}sufficient:{RESET} {_color_match(result.is_sufficient, expected['is_sufficient'])}"
        )
    if "missing_required" in expected:
        lines.append(
            f"  {DIM}missing:{RESET}  {_color_match(result.missing_required, expected['missing_required'])}"
        )

    if show_tokens:
        in_tok = result.input_tokens or 0
        out_tok = result.output_tokens or 0
        lines.append(
            f"  {DIM}tokens:{RESET}   input={CYAN}{in_tok}{RESET}, "
            f"output={CYAN}{out_tok}{RESET}, "
            f"total={BOLD}{CYAN}{in_tok + out_tok}{RESET}"
        )

    return passed, "\n".join(lines)


def discover_sample_sets(
    test_set: str = "all",
    scenario: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Auto-discover `tests/data/<decider>_samples.json` files and filter by set/scenario."""
    discovered: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(DATA_DIR.glob("*_samples.json")):
        decider_name = path.stem.removesuffix("_samples")
        if test_set not in ("all", decider_name):
            continue
        samples: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
        if scenario:
            needle = scenario.lower()
            samples = [s for s in samples if needle in s["id"].lower()]
        if samples:
            discovered[decider_name] = samples
    return discovered


def build_decider_suite(
    file_label: str,
    client_factory: Callable[[], DecisionClient],
    samples_by_set: dict[str, list[dict[str, Any]]],
    scoreboard: list[dict[str, Any]],
    token_totals: dict[str, int] | None = None,
) -> unittest.TestSuite:
    """Build a unittest.TestSuite for any DecisionClient across all discovered sample sets."""
    show_tokens = token_totals is not None

    class DeciderTestCase(unittest.TestCase):
        router: ConversationRouter

        @classmethod
        def setUpClass(cls) -> None:
            cls.router = ConversationRouter(client=client_factory())
            logger.debug(
                f"\n{BOLD}{CYAN}=== AuthorsIntent [{file_label}] Decider Tests ==={RESET}"
            )

        @classmethod
        def tearDownClass(cls) -> None:
            cls.router.close()

    def _make_method(
        decider_name: str, sample: dict[str, Any]
    ) -> Callable[[DeciderTestCase], None]:
        sample_id = sample["id"]
        state = sample["state"]
        expected = sample["expected"]

        def _test(self: DeciderTestCase) -> None:
            result = self.router.decide(decider_name, state)
            if token_totals is not None:
                token_totals["input"] += result.input_tokens or 0
                token_totals["output"] += result.output_tokens or 0
                token_totals["scenarios"] += 1

            passed, report = format_decision_report(
                file_label,
                decider_name,
                sample_id,
                state,
                result,
                expected,
                show_tokens=show_tokens,
            )
            if passed:
                logger.debug(report)
            else:
                logger.error(report)

            scoreboard.append(
                {"file": file_label, "set": decider_name, "id": sample_id, "passed": passed}
            )
            self.assertEqual(
                result.output, expected["output"], f"[{sample_id}] output mismatch"
            )
            for choice_key, exp_choice in expected.get("choices", {}).items():
                self.assertEqual(
                    result.choices.get(choice_key),
                    exp_choice,
                    f"[{sample_id}] choice {choice_key!r} mismatch",
                )
            if "is_sufficient" in expected:
                self.assertEqual(
                    result.is_sufficient,
                    expected["is_sufficient"],
                    f"[{sample_id}] is_sufficient mismatch",
                )
            if "missing_required" in expected:
                self.assertEqual(
                    result.missing_required,
                    expected["missing_required"],
                    f"[{sample_id}] missing_required mismatch",
                )

        _test.__doc__ = f"[{file_label}][{decider_name}] {sample_id}"
        return _test

    suite = unittest.TestSuite()
    for set_idx, (decider_name, samples) in enumerate(samples_by_set.items(), start=1):
        for idx, sample in enumerate(samples, start=1):
            method_name = (
                f"test_{file_label.lower()}_{set_idx:02d}_{decider_name}_{idx:02d}_{sample['id']}"
            )
            setattr(DeciderTestCase, method_name, _make_method(decider_name, sample))
            suite.addTest(DeciderTestCase(method_name))

    return suite


def _normalize_file_arg(raw: str) -> str:
    stem = Path(raw.strip()).stem.lower()
    if stem not in ("all", "core", "e2e"):
        raise argparse.ArgumentTypeError(
            f"Invalid --file value {raw!r}. Choose from: all, core, e2e (or core.py / e2e.py)."
        )
    return stem


def log_scoreboard(
    scoreboard: list[dict[str, Any]],
    token_totals: dict[str, int],
) -> None:
    if not scoreboard:
        return
    passed_count = sum(1 for item in scoreboard if item["passed"])
    failed_count = len(scoreboard) - passed_count

    lines = [f"\n{BOLD}{CYAN}=== Scenario Scoreboard ==={RESET}"]
    for item in scoreboard:
        badge = f"{GREEN}{BOLD}[PASS]{RESET}" if item["passed"] else f"{RED}{BOLD}[FAIL]{RESET}"
        lines.append(
            f"  {badge} {MAGENTA}[{item['file']:<4}]{RESET} "
            f"{CYAN}[{item['set']:<7}]{RESET} {BOLD}{item['id']}{RESET}"
        )

    summary_color = GREEN if failed_count == 0 else RED
    lines.append(
        f"\n{BOLD}Result:{RESET} {summary_color}{BOLD}{passed_count}/{len(scoreboard)} passed"
        f"{f' ({failed_count} failed)' if failed_count else ''}{RESET}"
    )

    if token_totals["scenarios"] > 0:
        total_tok = token_totals["input"] + token_totals["output"]
        lines.append(
            f"\n{BOLD}{CYAN}--- E2E Token Usage Summary ---{RESET}\n"
            f"  {DIM}Scenarios:{RESET} {token_totals['scenarios']}\n"
            f"  {DIM}Input:{RESET}     {CYAN}{token_totals['input']}{RESET} tokens\n"
            f"  {DIM}Output:{RESET}    {CYAN}{token_totals['output']}{RESET} tokens\n"
            f"  {DIM}Total:{RESET}     {BOLD}{CYAN}{total_tok}{RESET} tokens"
        )

    logger.info("\n".join(lines))


def run_cli(default_file: str = "all", argv: list[str] | None = None) -> int:
    from tests.core import build_core_suite
    from tests.e2e import build_e2e_suite

    available_sets = ["all"] + [
        p.stem.removesuffix("_samples") for p in sorted(DATA_DIR.glob("*_samples.json"))
    ]

    parser = argparse.ArgumentParser(
        description="Run AuthorsIntent decider and router test suites."
    )
    parser.add_argument(
        "--file",
        dest="test_file",
        type=_normalize_file_arg,
        default=default_file,
        help="Test file to run: 'core' (offline mock), 'e2e' (live Jev API), or 'all' (default: %(default)s).",
    )
    parser.add_argument(
        "--set",
        dest="test_set",
        choices=available_sets,
        default="all",
        help=f"Filter by decider test set: {', '.join(available_sets)} (default: all).",
    )
    parser.add_argument(
        "--scenario",
        "-k",
        dest="scenario",
        default=None,
        help="Filter to a specific scenario (or substring) within the selected file/set.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging (logs detailed per-scenario breakdowns).",
    )
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)

    samples_by_set = discover_sample_sets(test_set=args.test_set, scenario=args.scenario)
    if not samples_by_set:
        logger.warning(
            f"{YELLOW}No test scenarios matched --set={args.test_set!r} --scenario={args.scenario!r}.{RESET}"
        )
        return 1

    scoreboard: list[dict[str, Any]] = []
    token_totals = {"input": 0, "output": 0, "scenarios": 0}
    master_suite = unittest.TestSuite()

    files = ["core", "e2e"] if args.test_file == "all" else [args.test_file]
    for test_file in files:
        if test_file == "core":
            master_suite.addTest(
                build_core_suite(samples_by_set=samples_by_set, scoreboard=scoreboard)
            )
        elif test_file == "e2e":
            master_suite.addTest(
                build_e2e_suite(
                    samples_by_set=samples_by_set,
                    scoreboard=scoreboard,
                    token_totals=token_totals,
                )
            )

    runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
    result = runner.run(master_suite)
    log_scoreboard(scoreboard, token_totals)
    return 0 if result.wasSuccessful() else 1


def main() -> None:
    sys.exit(run_cli(default_file="all"))


if __name__ == "__main__":
    main()
