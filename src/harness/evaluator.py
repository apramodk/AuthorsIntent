"""Intent and STAR evaluator."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from src.engines.base import DecisionEngine

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"


@dataclass(frozen=True)
class IntentEvaluation:
    """Structured result of evaluating a segment against intent.json."""

    macro_intent: str
    micro_intent: str | None
    is_inform_prob: float
    is_persuade_prob: float
    has_micro_intent_prob: float
    micro_intent_probabilities: dict[str, float]
    raw_answers: dict[str, Any]


class IntentEvaluator:
    """Evaluates dialogue segments against the declarative intent.json schema."""

    def __init__(self, engine: DecisionEngine, schema_path: Path | None = None) -> None:
        self.engine = engine
        path = schema_path or (SCHEMAS_DIR / "intent.json")
        self.schema: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        self.questions: dict[str, Any] = self.schema["questions"]
        thresholds = self.schema.get("macro_derivation", {}).get("thresholds", {})
        self.yes_threshold: float = float(thresholds.get("yes", 0.7))
        self.no_threshold: float = float(thresholds.get("no", 0.3))

    def evaluate_segment(
        self,
        segment: str,
        conversation_context: str | None = None,
    ) -> IntentEvaluation:
        """Send segment state and intent questions to the DecisionEngine and derive intents."""
        state: dict[str, Any] = {"segment": segment}
        if conversation_context:
            state["conversation_context"] = conversation_context

        response = self.engine.evaluate(state=state, questions=self.questions)
        answers = response.get("answers", response)

        is_inform_prob = float(answers["is_inform"]["noul"])
        is_persuade_prob = float(answers["is_persuade"]["noul"])
        has_micro_prob = float(answers["has_micro_intent"]["noul"])

        micro_answer = answers["micro_intent"]
        top_micro = str(micro_answer["choice"])
        micro_probs = {
            k: float(v) for k, v in micro_answer.get("probabilities", {}).items()
        }

        macro_intent = self.derive_macro_intent(is_inform_prob, is_persuade_prob)
        micro_intent = top_micro if has_micro_prob >= self.yes_threshold else None

        return IntentEvaluation(
            macro_intent=macro_intent,
            micro_intent=micro_intent,
            is_inform_prob=is_inform_prob,
            is_persuade_prob=is_persuade_prob,
            has_micro_intent_prob=has_micro_prob,
            micro_intent_probabilities=micro_probs,
            raw_answers=answers,
        )

    def derive_macro_intent(self, is_inform_prob: float, is_persuade_prob: float) -> str:
        """Apply the truth table to derive Macro Intent from atomic Noul probabilities."""
        inform_yes = is_inform_prob >= self.yes_threshold
        persuade_yes = is_persuade_prob >= self.yes_threshold

        if inform_yes and persuade_yes:
            return "BOTH"
        if inform_yes and not persuade_yes:
            return "INFORM"
        if persuade_yes and not inform_yes:
            return "PERSUADE"
        return "AMBIGUOUS"
