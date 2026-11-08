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
│   │   ├── intent.json         # Typed questions & criteria for macro/micro intent
│   │   ├── star.json           # Typed questions & criteria for STAR verification
│   │   └── routing.json        # Routing thresholds & decision rules
│   ├── engines/
│   │   ├── base.py             # Abstract DecisionEngine interface
│   │   └── jev_engine.py       # TypeSafe Jev DecisionEngine implementation
│   └── harness/
│       ├── segmenter.py        # Dialogue turn & clause segmentation
│       ├── evaluator.py        # Runs schemas against state via the DecisionEngine
│       └── router.py           # Truth-table routing logic over calibrated probabilities
└── tests/
    ├── data/
    │   └── intent_samples.json # Mock test utterances, Jev probabilities, and expected routes
    └── intent.py               # Offline unit tests & live Jev probe runner
```

---

## Contributor Setup

### 1. Prerequisites
- Python `>=3.11`
- [`uv`](https://docs.astral.sh/uv/) package manager
- A TypeSafe API key (only required for live API testing against **Jev**)

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

For live testing against TypeSafe's Jev API, create a `.env` file in the project root (ignored by git):

```bash
JEV_KEY=your_typesafe_api_key_here
```

*(Note: `JevEngine` checks `JEV_KEY` first and falls back to `TYPESAFE_API_KEY`.)*

---

## Running Tests

### 1. Offline Unit Tests (Mock Engine)
Runs fast, deterministic tests against the pre-recorded Jev probability distributions in `tests/data/intent_samples.json` to verify schema loading, Noul threshold derivation, and truth-table routing:

```bash
uv run python tests/intent.py
# or directly with the venv interpreter:
.venv/bin/python tests/intent.py
```

### 2. Live API Probe (TypeSafe Jev)
Sends the sample utterances in `tests/data/intent_samples.json` to the live TypeSafe System One API (`https://api.typesafe.ai/v1/systemone`) using `JEV_KEY` from `.env`, printing out calibrated Noul probabilities and comparing actual vs. expected routes:

```bash
uv run python tests/intent.py --live
# or directly with the venv interpreter:
.venv/bin/python tests/intent.py --live
```

### 3. Adding New Test Cases or Dependencies
- **Add test cases:** Append new sample objects (`id`, `state`, `mock_answers`, `expected`) to `tests/data/intent_samples.json`.
- **Add a package:** Run `uv add <package>` (or `uv add --dev <package>`), which automatically updates both `pyproject.toml` and `uv.lock`.
