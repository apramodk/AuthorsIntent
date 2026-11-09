"""Shared logging, formatting, and CLI runner for `tests/decider/core.py` and `tests/decider/e2e.py`."""

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.harness.deciderFactory import DecisionResult
from src.harness.router import RouteDecision

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
INTENT_SAMPLES_PATH = DATA_DIR / "intent_samples.json"
STAR_SAMPLES_PATH = DATA_DIR / "star_samples.json"

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


def format_intent_report(
    file_label: str,
    sample_id: str,
    segment: str,
    result: DecisionResult,
    decision: RouteDecision,
    expected: dict[str, Any],
    show_tokens: bool = False,
) -> tuple[bool, str]:
    micro = result.choices.get("micro_intent")
    passed = (
        result.output == expected["macro_intent"]
        and micro == expected["micro_intent"]
        and decision.route == expected["route"]
        and decision.requires_star_verification == expected["requires_star_verification"]
    )
    badge = f"{GREEN}{BOLD}[PASS]{RESET}" if passed else f"{RED}{BOLD}[FAIL]{RESET}"
    probs = result.probabilities
    lines = [
        f"\n{badge} {MAGENTA}[{file_label}]{RESET} {CYAN}{BOLD}[intent] {sample_id}{RESET}",
        f"  {DIM}segment:{RESET}  {segment}",
        f"  {DIM}nouls:{RESET}    is_inform={_color_prob(probs['is_inform'])}, "
        f"is_persuade={_color_prob(probs['is_persuade'])}, "
        f"has_micro={_color_prob(probs['has_micro_intent'])}",
        f"  {DIM}macro:{RESET}    {_color_match(result.output, expected['macro_intent'])}",
        f"  {DIM}micro:{RESET}    {_color_match(micro, expected['micro_intent'])}",
        f"  {DIM}strategy:{RESET} {MAGENTA}{decision.strategy_name}{RESET} -> "
        f"{_color_match(decision.route, expected['route'])} "
        f"{DIM}[STAR={_color_match(decision.requires_star_verification, expected['requires_star_verification'])}]{RESET}",
    ]
    if show_tokens:
        in_tok = result.input_tokens or 0
        out_tok = result.output_tokens or 0
        lines.append(
            f"  {DIM}tokens:{RESET}   input={CYAN}{in_tok}{RESET}, "
            f"output={CYAN}{out_tok}{RESET}, "
            f"total={BOLD}{CYAN}{in_tok + out_tok}{RESET}"
        )
    return passed, "\n".join(lines)


def format_star_report(
    file_label: str,
    sample_id: str,
    segment: str,
    result: DecisionResult,
    decision: RouteDecision,
    expected: dict[str, Any],
    show_tokens: bool = False,
) -> tuple[bool, str]:
    passed = (
        result.is_sufficient == expected["is_sufficient"]
        and result.output == expected["status"]
        and result.missing_required == expected["missing_required"]
        and decision.route == expected["route"]
    )
    badge = f"{GREEN}{BOLD}[PASS]{RESET}" if passed else f"{RED}{BOLD}[FAIL]{RESET}"
    probs = result.probabilities
    lines = [
        f"\n{badge} {MAGENTA}[{file_label}]{RESET} {CYAN}{BOLD}[star] {sample_id}{RESET}",
        f"  {DIM}segment:{RESET}  {segment}",
        f"  {DIM}star:{RESET}     S={_color_prob(probs['has_situation'])}, "
        f"T={_color_prob(probs['has_task'])}, "
        f"A={_color_prob(probs['has_action'])}, "
        f"R={_color_prob(probs['has_result'])} | "
        f"structured={_color_prob(probs['is_structured'])}",
        f"  {DIM}status:{RESET}   {_color_match(result.output, expected['status'])} "
        f"{DIM}[is_sufficient={_color_match(result.is_sufficient, expected['is_sufficient'])}]{RESET}",
        f"  {DIM}missing:{RESET}  {_color_match(result.missing_required, expected['missing_required'])}",
        f"  {DIM}strategy:{RESET} {MAGENTA}{decision.strategy_name}{RESET} -> "
        f"{_color_match(decision.route, expected['route'])}",
    ]
    if show_tokens:
        in_tok = result.input_tokens or 0
        out_tok = result.output_tokens or 0
        lines.append(
            f"  {DIM}tokens:{RESET}   input={CYAN}{in_tok}{RESET}, "
            f"output={CYAN}{out_tok}{RESET}, "
            f"total={BOLD}{CYAN}{in_tok + out_tok}{RESET}"
        )
    return passed, "\n".join(lines)


def _normalize_file_arg(raw: str) -> str:
    """Normalize `--file` value (e.g., `core.py` -> `core`, `tests/decider/e2e.py` -> `e2e`)."""
    stem = Path(raw.strip()).stem.lower()
    if stem not in ("all", "core", "e2e"):
        raise argparse.ArgumentTypeError(
            f"Invalid --file value {raw!r}. Choose from: all, core, e2e (or core.py / e2e.py)."
        )
    return stem


def load_filtered_samples(
    test_set: str = "all",
    scenario: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load intent and star samples filtered by `--set` and `--scenario`."""
    intent_samples: list[dict[str, Any]] = []
    star_samples: list[dict[str, Any]] = []

    if test_set in ("all", "intent"):
        intent_samples = json.loads(INTENT_SAMPLES_PATH.read_text(encoding="utf-8"))
    if test_set in ("all", "star"):
        star_samples = json.loads(STAR_SAMPLES_PATH.read_text(encoding="utf-8"))

    if scenario:
        needle = scenario.lower()
        intent_samples = [
            s for s in intent_samples if needle in s["id"].lower()
        ]
        star_samples = [
            s for s in star_samples if needle in s["id"].lower()
        ]

    return intent_samples, star_samples


def log_scoreboard(
    scoreboard: list[dict[str, Any]],
    token_totals: dict[str, int],
) -> None:
    """Log a compact color-coded summary table of all executed scenarios."""
    if not scoreboard:
        return
    passed_count = sum(1 for item in scoreboard if item["passed"])
    failed_count = len(scoreboard) - passed_count

    lines = [f"\n{BOLD}{CYAN}=== Scenario Scoreboard ==={RESET}"]
    for item in scoreboard:
        badge = f"{GREEN}{BOLD}[PASS]{RESET}" if item["passed"] else f"{RED}{BOLD}[FAIL]{RESET}"
        lines.append(
            f"  {badge} {MAGENTA}[{item['file']:<4}]{RESET} "
            f"{CYAN}[{item['set']:<6}]{RESET} {BOLD}{item['id']}{RESET}"
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
    from tests.decider.core import build_core_suite
    from tests.decider.e2e import build_e2e_suite

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
        choices=["all", "intent", "star"],
        default="all",
        help="Filter by decider test set: 'intent', 'star', or 'all' (default: all).",
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

    intent_samples, star_samples = load_filtered_samples(
        test_set=args.test_set,
        scenario=args.scenario,
    )
    if not intent_samples and not star_samples:
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
                build_core_suite(
                    intent_samples=intent_samples,
                    star_samples=star_samples,
                    scoreboard=scoreboard,
                )
            )
        elif test_file == "e2e":
            master_suite.addTest(
                build_e2e_suite(
                    intent_samples=intent_samples,
                    star_samples=star_samples,
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
