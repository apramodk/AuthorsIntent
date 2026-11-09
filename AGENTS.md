# AuthorsIntent Architecture & Schema Spec

## Core Objective
Build a modular conversation routing service using a System One decision client (starting with TypeSafe Jev, swapping to OpenJev later).

## Intent Taxonomy (`src/schemas/intent.json`)
- **Macro Intent (Author's Purpose):**
  - `INFORM`: User provides context, state updates, or background constraints.
  - `PERSUADE`: User issues commands, tasks, or desired outcomes.
  - `BOTH`: Hybrid prompts.
- **Operational Micro Intents:**
  - `request_info`, `clarify_point`, `provide_update`, `confirm_understanding`, `validate_info`.

## Topic Segmentation (`src/schemas/segment.json`)
- Evaluate candidate dialogue turns against a sliding window (`window_size=2` turns) of the active segment:
  - `CONTINUE_SEGMENT`: Turn continues or directly responds to the active topic.
  - `NEW_SEGMENT`: Turn pivots to an unrelated task or topic.
  - `COMPOUND_SHIFT`: Turn closes out the active topic and introduces a new topic in the same message.
  - `AMBIGUOUS_BOUNDARY`: Brief acknowledgments or filler turns.

## Verification Framework — STAR (`src/schemas/star.json`)
- Evaluate dialogue segments for completeness against STAR (Situation, Task, Action, Result).
- Minimum execution threshold: `Situation` and `Task` must be present (`is_sufficient`).
- If incomplete:
  - Missing parameters: Trigger targeted clarification (`CLARIFY_PARAMETERS`).
  - Vague / unstructured: Switch to scaffolding persona to guide the user (`SCAFFOLD_USER`).

## Repository Structure & Conventions
- `src/schemas/`: `intent.json`, `star.json`, `segment.json`
- `src/clients/`: `base.py` (abstract `DecisionClient` interface), `jevClient.py` (`JevClient`)
- `src/deciders/`: `deciderFactory.py`, `deciderManager.py`
- `src/router.py`: `ConversationRouter` (main entry point re-exported by `src/__init__.py`)
- `tests/`: `core.py`, `e2e.py`, `runner.py`, and `tests/data/*_samples.json`
- **Conventions:** Use `camelCase` for multi-word Python filenames, keep `__init__.py` minimal (re-exports only), and define routing logic declaratively in `src/schemas/*.json`. See `CONTRIBUTING.md` for full setup and conventions.
