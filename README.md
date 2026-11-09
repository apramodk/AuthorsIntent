# AuthorsIntent

A modular conversation routing harness powered by a System One decision engine (starting with TypeSafe's **Jev**, designed to swap cleanly to **OpenJev**).

Instead of relying on brittle heuristics or open-ended LLM prompt-and-parse steps to route user turns, **AuthorsIntent** decomposes dialogue turns into typed judgments—classifying authorial intent and verifying prompt completeness against the **STAR** framework—while keeping routing decisions explicit and testable in code.

---

## Architecture Overview

### 1. Intent Taxonomy
- **Macro Intent (Author's Purpose):**
  - `INFORM`: User provides context, state updates, or background constraints.
  - `PERSUADE`: User issues commands, tasks, or desired outcomes.
  - `BOTH`: Hybrid prompts combining context and actionable requests.
- **Operational Micro Intents:**
  - `request_info`
  - `clarify_point`
  - `provide_update`
  - `confirm_understanding`
  - `validate_info`

### 2. Verification Framework (STAR)
Dialogue segments are evaluated for completeness against **STAR** (**S**ituation, **T**ask, **A**ction, **R**esult):
- **Minimum Execution Threshold (`is_sufficient`):** Both `Situation` and `Task` must be present.
- **Incomplete Handling:**
  - *Missing parameters:* Trigger targeted clarification questions.
  - *Vague / unstructured:* Switch to a scaffolding persona to guide the user in structuring their request.

---

## Repository Structure

```text
├── src/
│   ├── schemas/
│   │   ├── intent.json         # Typed Jev questions & truth-table rules for macro/micro intent
│   │   ├── star.json           # Typed Jev questions & truth-table rules for STAR verification
│   │   └── segment.json        # Typed Jev questions & truth-table rules for topic segmentation
│   ├── engines/
│   │   ├── base.py             # Abstract DecisionEngine interface
│   │   └── jev_engine.py       # TypeSafe Jev DecisionEngine implementation (typesafe-sdk)
│   └── harness/
│       ├── deciderFactory.py   # Generic JSON-driven Decider & DeciderFactory
│       ├── deciderManager.py   # DeciderManager registry creating decider instances per schema
│       └── router.py           # ConversationRouter over DeciderManager outputs
└── tests/
    ├── data/
    │   ├── intent_samples.json  # Intent test utterances, mock Jev probabilities, and expected routes
    │   ├── star_samples.json    # STAR test utterances, mock Jev probabilities, and expected routes
    │   └── segment_samples.json # Topic boundary test threads, mock Jev probabilities, and outputs
    └── decider/
        ├── core.py             # Unified offline core unit tests for DeciderManager, Decider & Router
        └── e2e.py              # Unified live E2E tests against TypeSafe Jev
```

---

## Contributor Setup

### 1. Prerequisites
- Python `>=3.11`
- [`uv`](https://docs.astral.sh/uv/) package manager
- A TypeSafe API key (only required for live E2E testing against **Jev**)

### 2. Environment Setup

Clone the repository, create the virtual environment, and sync dependencies with `uv`:

```bash
git clone <repo-url>
cd AuthorsIntent

# Create .venv and install dependencies from pyproject.toml / uv.lock
uv venv
uv sync
```

*(Optional)* Activate the virtual environment in your shell:

```bash
source .venv/bin/activate
```

### 3. Configuring API Keys (`.env`)

Copy `.example.env` to `.env` in the project root (ignored by git) and set your TypeSafe Jev API key:

```bash
cp .example.env .env
```

```dotenv
JEV_KEY=your_typesafe_api_key_here
```

*(Note: `JevEngine` checks `JEV_KEY` first and falls back to `TYPESAFE_API_KEY`.)*

---

## Running Tests

### 1. Run Everything (`uv run test`)
Runs both offline core tests (`core.py`) and live Jev E2E tests (`e2e.py`) across all decider sets (`intent` and `star`), printing a color-coded **Scenario Scoreboard** at the end:

```bash
uv run test
```

### 2. Filtering by `--file`, `--set`, or `--scenario`
You can filter by test file (`core` or `e2e`), decider test set (`intent` or `star`), and/or a specific scenario ID or substring:

```bash
# Offline core tests only
uv run test --file core
# (or: uv run python tests/decider/core.py)

# Live Jev E2E tests only
uv run test --file e2e
# (or: uv run python tests/decider/e2e.py)

# Run only the STAR test set (or --set intent)
uv run test --file core --set star

# Run a specific scenario in a file or set
uv run test --file core --set star --scenario star_missing_action
uv run test --file e2e --set intent --scenario confirm_understanding

# Add -v / --verbose to log detailed per-scenario breakdowns (segments, Noul probs, strategies)
uv run test --file core -v
```

### 3. Adding New Test Cases or Dependencies
- **Add test cases:** Append new sample objects (`id`, `state`, `mock_answers`, `expected`) to `tests/data/intent_samples.json`.
- **Add a package:** Run `uv add <package>` (or `uv add --dev <package>`), which automatically updates both `pyproject.toml` and `uv.lock`.
