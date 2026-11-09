# Contributing to AuthorsIntent

## 1. Environment Setup

### Prerequisites
- Python `>=3.11`
- [`uv`](https://docs.astral.sh/uv/) package manager
- A TypeSafe API key (only required for live E2E tests against **Jev**)

### Install Dependencies
```bash
git clone https://github.com/apramodk/AuthorsIntent.git
cd AuthorsIntent

uv venv
uv sync
```

### Configure API Keys (`.env`)
Copy `.example.env` to `.env` in the project root (ignored by git) and add your TypeSafe API key:

```bash
cp .example.env .env
```

```dotenv
JEV_KEY=your_typesafe_api_key_here
```

*(Note: `JevClient` checks `JEV_KEY` first and falls back to `TYPESAFE_API_KEY`.)*

---

## 2. Codebase Conventions & Style Rules

- **File Naming (`camelCase`):** Multi-word Python modules use `camelCase` (e.g., `jevClient.py`, `deciderFactory.py`, `deciderManager.py`). Single-word modules remain lowercase (`router.py`, `base.py`, `core.py`, `e2e.py`, `runner.py`).
- **Keep `__init__.py` Minimal:** Entry-point `__init__.py` files should only re-export public classes/types (e.g., `src/__init__.py` re-exports `ConversationRouter` and `RouteDecision` from `src/router.py`). Keep implementation logic in dedicated modules.
- **Declarative Schemas Over Boilerplate Classes:** New classification or verification dimensions belong in `src/schemas/<name>.json` (defining `questions`, `rules`, `default_output`, and optional `sufficient_when`), not in ad-hoc Python strategy classes or string-mapping tables.
- **Client Interface (`src/clients/base.py`):** All model clients (`JevClient`, future `OpenJevClient`, test mocks) must inherit from `DecisionClient` and implement `evaluate(state, questions) -> dict`.
- **Dependency Management:** Always use `uv add <package>` (or `uv add --dev <package>`) so `pyproject.toml` and `uv.lock` stay synchronized.

---

## 3. Running Tests

The test suite is driven by `tests/runner.py`, which auto-discovers every `tests/data/*_samples.json` file and pairs it with its matching `src/schemas/<name>.json` schema.

```bash
# Run all tests (offline core + live E2E)
uv run test

# Run offline core unit tests only (no API calls)
uv run test --file core

# Run live Jev E2E tests only (requires JEV_KEY)
uv run test --file e2e

# Filter by schema set (intent, segment, or star)
uv run test --file core --set segment

# Filter by a specific scenario ID or substring
uv run test --file core --set star --scenario star_missing_action

# Verbose output (prints inputs, Noul probabilities, and rule outputs)
uv run test --file core -v
```

---

## 4. Adding a New Decider or Test Case

1. **Add a Test Sample:** Append a new entry (`id`, `state`, `mock_answers`, `expected`) to `tests/data/<name>_samples.json`. The `expected` block maps directly to `DecisionResult` fields (`output`, `choices`, `is_sufficient`, `missing_required`).
2. **Add a New Schema:**
   - Create `src/schemas/<name>.json`.
   - Create `tests/data/<name>_samples.json`.
   - `DeciderManager` and `tests/runner.py` will discover it automatically.
