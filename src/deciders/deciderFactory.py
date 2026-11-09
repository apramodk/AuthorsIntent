"""Generic JSON-driven Decider and DeciderFactory."""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from src.clients.base import DecisionClient


@dataclass(frozen=True)
class DecisionResult:
    """Standardized output produced by a Decider from any declarative JSON schema."""

    decider_name: str
    output: str
    booleans: dict[str, bool]
    probabilities: dict[str, float]
    choices: dict[str, str | None] = field(default_factory=dict)
    choice_probabilities: dict[str, dict[str, float]] = field(default_factory=dict)
    is_sufficient: bool | None = None
    missing_required: list[str] = field(default_factory=list)
    raw_answers: dict[str, Any] = field(default_factory=dict)
    input_tokens: int | None = None
    output_tokens: int | None = None


class Decider:
    """Generic decider driven by a declarative JSON schema (questions, thresholds, gating, rules)."""

    def __init__(self, schema: dict[str, Any], client: DecisionClient) -> None:
        self.schema = schema
        self.client = client
        self.name: str = str(schema.get("name", "unnamed"))
        self.questions: dict[str, Any] = schema["questions"]

        thresholds = schema.get("thresholds", {})
        self.yes_threshold: float = float(thresholds.get("yes", 0.7))
        self.no_threshold: float = float(thresholds.get("no", 0.3))

        self.gating: dict[str, str] = dict(schema.get("gating", {}))
        self.required_nouls: dict[str, str] = dict(schema.get("required_nouls", {}))
        self.rules: list[dict[str, Any]] = list(schema.get("rules", []))
        self.default_output: str = str(schema.get("default_output", "UNKNOWN"))

    def decide(self, state: dict[str, Any]) -> DecisionResult:
        """Evaluate the schema's questions against `state` and apply its truth-table rules."""
        response = self.client.evaluate(state=state, questions=self.questions)
        answers = response.get("answers", response)
        usage = response.get("usage") or {}
        return self.apply_rules(answers=answers, usage=usage)

    def apply_rules(
        self,
        answers: dict[str, Any],
        usage: dict[str, Any] | None = None,
    ) -> DecisionResult:
        """Apply thresholds, companion-Noul gating, required checks, and ordered truth-table rules."""
        usage_dict = usage or {}
        input_tokens = usage_dict.get("input_tokens")
        output_tokens = usage_dict.get("output_tokens")

        probabilities: dict[str, float] = {}
        booleans: dict[str, bool] = {}
        choices: dict[str, str | None] = {}
        choice_probabilities: dict[str, dict[str, float]] = {}

        # 1. Extract Noul probabilities/booleans and Choice selections
        for q_id, q_spec in self.questions.items():
            q_type = q_spec.get("type")
            ans = answers[q_id]
            if q_type == "noul":
                prob = float(ans["noul"])
                probabilities[q_id] = prob
                booleans[q_id] = prob >= self.yes_threshold
            elif q_type == "choice":
                choices[q_id] = str(ans["choice"])
                choice_probabilities[q_id] = {
                    k: float(v) for k, v in ans.get("probabilities", {}).items()
                }

        # 2. Apply companion-Noul gating for choice questions
        for choice_q, gate_noul in self.gating.items():
            if choice_q in choices and not booleans.get(gate_noul, False):
                choices[choice_q] = None

        # 3. Evaluate required_nouls if declared by schema (e.g., STAR Situation & Task)
        missing_required: list[str] = []
        is_sufficient: bool | None = None
        if self.required_nouls:
            missing_required = [
                label
                for label, noul_id in self.required_nouls.items()
                if not booleans.get(noul_id, False)
            ]
            is_sufficient = len(missing_required) == 0

        # 4. Evaluate ordered truth-table rules (first matching `when` clause wins)
        output = self.default_output
        for rule in self.rules:
            when_clause: dict[str, Any] = rule.get("when", {})
            if all(booleans.get(k) == expected_val for k, expected_val in when_clause.items()):
                output = str(rule["output"])
                break

        return DecisionResult(
            decider_name=self.name,
            output=output,
            booleans=booleans,
            probabilities=probabilities,
            choices=choices,
            choice_probabilities=choice_probabilities,
            is_sufficient=is_sufficient,
            missing_required=missing_required,
            raw_answers=answers,
            input_tokens=int(input_tokens) if input_tokens is not None else None,
            output_tokens=int(output_tokens) if output_tokens is not None else None,
        )


class DeciderFactory:
    """Factory for creating Decider instances from JSON schema dictionaries or files."""

    @staticmethod
    def from_dict(schema: dict[str, Any], client: DecisionClient) -> Decider:
        """Instantiate a Decider from a parsed JSON schema dictionary."""
        return Decider(schema=schema, client=client)

    @staticmethod
    def from_file(path: Path, client: DecisionClient) -> Decider:
        """Load a JSON schema file and instantiate a Decider."""
        schema = json.loads(path.read_text(encoding="utf-8"))
        if "name" not in schema:
            schema["name"] = path.stem
        return Decider(schema=schema, client=client)
