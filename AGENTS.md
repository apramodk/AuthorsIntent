# AuthorsIntent Architecture & Schema Spec

## Core Objective
Build a modular conversation routing harness using a decision engine (starting with typesafe Jev, swapping to OpenJev later).

## Intent Taxonomy
- **Macro Intent (Author's Purpose):**
  - `INFORM`: User provides context, state updates, or background constraints.
  - `PERSUADE`: User issues commands, tasks, or desired outcomes.
  - `BOTH`: Hybrid prompts.
- **Operational Micro Intents:**
  - `request_info`, `clarify_point`, `provide_update`, `confirm_understanding`, `validate_info`.

## Verification Framework (STAR)
- Evaluate dialogue segments for completeness against STAR (Situation, Task, Action, Result).
- Minimum execution threshold: `Situation` and `Task` must be present (`is_sufficient`).
- If incomplete:
  - Missing parameters: Trigger targeted clarification.
  - Vague / unstructured: Switch to scaffolding persona to guide the user.

## Repository Structure
- `src/schemas/`: `intent.json`, `star.json`
- `src/engines/`: `base.py` (abstract `DecisionEngine`), `jev_engine.py`
- `src/harness/`: `segmenter.py`, `deciderFactory.py`, `deciderManager.py`, `router.py`
- `tests/decider/`: `core.py`, `e2e.py`
