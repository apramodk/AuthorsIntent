# AuthorsIntent

A modular conversation routing service powered by a System One decision client (starting with TypeSafe's **Jev**, designed to swap cleanly to **OpenJev**).

Instead of relying on brittle heuristics or open-ended LLM prompt-and-parse steps to route user turns, **AuthorsIntent** decomposes dialogue into typed judgments—segmenting multi-turn threads by topic, classifying authorial intent, and verifying prompt completeness against the **STAR** framework.

---

## Architecture Overview

### 1. Topic Segmentation (`src/schemas/segment.json`)
Evaluates incoming turns against a sliding window (`window_size=2`) of the active topic segment:
- `CONTINUE_SEGMENT`: Continues or answers the active topic.
- `NEW_SEGMENT`: Pivots to an unrelated topic or task.
- `COMPOUND_SHIFT`: Wraps up the previous topic and introduces a new one in the same message.
- `AMBIGUOUS_BOUNDARY`: Brief acknowledgments or filler turns.

### 2. Intent Taxonomy (`src/schemas/intent.json`)
- **Macro Intent (Author's Purpose):**
  - `INFORM`: User provides context, state updates, or background constraints.
  - `PERSUADE`: User issues commands, tasks, or desired outcomes.
  - `BOTH`: Hybrid prompts combining context and actionable requests.
- **Operational Micro Intents:**
  - `request_info`, `clarify_point`, `provide_update`, `confirm_understanding`, `validate_info`.

### 3. Verification Framework — STAR (`src/schemas/star.json`)
Dialogue segments are evaluated for completeness against **STAR** (**S**ituation, **T**ask, **A**ction, **R**esult):
- **Minimum Execution Threshold (`is_sufficient`):** Both `Situation` and `Task` must be present.
- **Incomplete Handling:**
  - `CLARIFY_PARAMETERS`: Trigger targeted clarification for missing `Situation` or `Task`.
  - `SCAFFOLD_USER`: Switch to a scaffolding persona when the prompt is vague or unstructured.

---

## Repository Structure

```text
├── src/
│   ├── __init__.py             # Re-exports ConversationRouter & RouteDecision
│   ├── router.py               # ConversationRouter main entry point
│   ├── schemas/
│   │   ├── intent.json         # Typed Jev questions & rules for macro/micro intent
│   │   ├── star.json           # Typed Jev questions & rules for STAR verification
│   │   └── segment.json        # Typed Jev questions & rules for topic segmentation
│   ├── clients/
│   │   ├── base.py             # Abstract DecisionClient interface
│   │   └── jevClient.py        # TypeSafe Jev DecisionClient implementation
│   └── deciders/
│       ├── deciderFactory.py   # Generic JSON-driven Decider & DeciderFactory
│       └── deciderManager.py   # DeciderManager registry creating deciders per schema
└── tests/
    ├── data/
    │   ├── intent_samples.json
    │   ├── star_samples.json
    │   └── segment_samples.json
    ├── core.py                 # Offline core unit tests
    ├── e2e.py                  # Live E2E tests against TypeSafe Jev
    └── runner.py               # Shared CLI test runner & scoreboard
```

---

## Quick Start

```python
from src import ConversationRouter

router = ConversationRouter()

# Route a single turn (Intent + STAR verification)
decision = router.route(
    "Our `/v1/search` endpoint in `src/api/search.py` takes 1.4s on average. "
    "Can you optimize the query so p95 drops under 150ms?"
)
print(decision.intent.output)       # "BOTH"
print(decision.star.output)         # "MISSING_ACTION"
print(decision.star.is_sufficient)  # True

# Segment and route a multi-turn conversation thread
routes = router.route_thread(
    "User: Webhook worker is throwing KeyError on guest checkout.\n"
    "Assistant: Check where customer.subscription_id is parsed.\n"
    "User: Also, how do we configure dark mode in the dashboard?"
)
```

---

## Contributing & Running Tests

See [CONTRIBUTING.md](CONTRIBUTING.md) for environment setup (`uv`), `.env` configuration, test runner CLI flags (`uv run test`), and codebase conventions (`camelCase` filenames, declarative schema design).
