"""Strategy-pattern conversation router operating over DeciderManager DecisionResults."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from src.harness.deciderFactory import DecisionResult
from src.harness.deciderManager import DeciderManager


@dataclass(frozen=True)
class RouteDecision:
    """Routing decision produced by a RoutingStrategy."""

    route: str
    strategy_name: str
    macro_intent: str
    micro_intent: str | None
    requires_star_verification: bool
    maintain_context: bool
    star_status: str | None = None
    is_sufficient: bool | None = None
    missing_required: list[str] | None = None
    reason: str = ""


class RoutingStrategy(ABC):
    """Abstract base class for routing strategies selected from decider labels."""

    @abstractmethod
    def build_decision(
        self,
        intent_result: DecisionResult,
        star_result: DecisionResult | None = None,
    ) -> RouteDecision:
        """Produce a RouteDecision from the labeled intent and optional STAR results."""
        raise NotImplementedError


class ContextMaintenanceStrategy(RoutingStrategy):
    """Strategy for pure INFORM turns: routes to context maintenance agent without STAR check."""

    def build_decision(
        self,
        intent_result: DecisionResult,
        star_result: DecisionResult | None = None,
    ) -> RouteDecision:
        micro = intent_result.choices.get("micro_intent")
        route_name = f"ingest_{micro}" if micro else "ingest_context"
        return RouteDecision(
            route=route_name,
            strategy_name=self.__class__.__name__,
            macro_intent=intent_result.output,
            micro_intent=micro,
            requires_star_verification=False,
            maintain_context=True,
            reason="User is informing/updating context without requesting task execution.",
        )


class LightweightValidationStrategy(RoutingStrategy):
    """Strategy for confirm_understanding / validate_info checks on existing context."""

    def build_decision(
        self,
        intent_result: DecisionResult,
        star_result: DecisionResult | None = None,
    ) -> RouteDecision:
        micro = intent_result.choices.get("micro_intent")
        return RouteDecision(
            route=f"handle_{micro}",
            strategy_name=self.__class__.__name__,
            macro_intent=intent_result.output,
            micro_intent=micro,
            requires_star_verification=False,
            maintain_context=(intent_result.output == "BOTH"),
            reason=f"Actionable {micro} check on existing context.",
        )


class AmbiguousFallbackStrategy(RoutingStrategy):
    """Strategy when neither INFORM nor PERSUADE crosses threshold."""

    def build_decision(
        self,
        intent_result: DecisionResult,
        star_result: DecisionResult | None = None,
    ) -> RouteDecision:
        micro = intent_result.choices.get("micro_intent")
        route_name = f"fallback_{micro}" if micro else "clarify_or_acknowledge"
        return RouteDecision(
            route=route_name,
            strategy_name=self.__class__.__name__,
            macro_intent=intent_result.output,
            micro_intent=micro,
            requires_star_verification=False,
            maintain_context=False,
            reason="Neither inform nor persuade crossed threshold.",
        )


class DirectExecuteStrategy(RoutingStrategy):
    """Strategy when S, T, A, and R are all present (COMPLETE_STAR)."""

    def build_decision(
        self,
        intent_result: DecisionResult,
        star_result: DecisionResult | None = None,
    ) -> RouteDecision:
        assert star_result is not None
        return RouteDecision(
            route="direct_execute",
            strategy_name=self.__class__.__name__,
            macro_intent=intent_result.output,
            micro_intent=intent_result.choices.get("micro_intent"),
            requires_star_verification=True,
            maintain_context=(intent_result.output == "BOTH"),
            star_status=star_result.output,
            is_sufficient=star_result.is_sufficient,
            missing_required=star_result.missing_required,
            reason="Full STAR specification (S, T, A, R) provided; executing directly.",
        )


class ConfirmCriteriaStrategy(RoutingStrategy):
    """Strategy when S, T, and A are present, but R is omitted (MISSING_RESULT)."""

    def build_decision(
        self,
        intent_result: DecisionResult,
        star_result: DecisionResult | None = None,
    ) -> RouteDecision:
        assert star_result is not None
        return RouteDecision(
            route="confirm_criteria_or_execute",
            strategy_name=self.__class__.__name__,
            macro_intent=intent_result.output,
            micro_intent=intent_result.choices.get("micro_intent"),
            requires_star_verification=True,
            maintain_context=(intent_result.output == "BOTH"),
            star_status=star_result.output,
            is_sufficient=star_result.is_sufficient,
            missing_required=star_result.missing_required,
            reason="S, T, and A are present, but Result criteria (R) are unspecified.",
        )


class ProposeActionPlanStrategy(RoutingStrategy):
    """Strategy when S, T, and R are present, but A is omitted (MISSING_ACTION)."""

    def build_decision(
        self,
        intent_result: DecisionResult,
        star_result: DecisionResult | None = None,
    ) -> RouteDecision:
        assert star_result is not None
        return RouteDecision(
            route="propose_action_plan",
            strategy_name=self.__class__.__name__,
            macro_intent=intent_result.output,
            micro_intent=intent_result.choices.get("micro_intent"),
            requires_star_verification=True,
            maintain_context=(intent_result.output == "BOTH"),
            star_status=star_result.output,
            is_sufficient=star_result.is_sufficient,
            missing_required=star_result.missing_required,
            reason="S, T, and R are present, but Action method (A) is unspecified; propose plan.",
        )


class PlanThenExecuteStrategy(RoutingStrategy):
    """Strategy when minimum S and T are present, while A and R are open (MINIMUM_SUFFICIENT)."""

    def build_decision(
        self,
        intent_result: DecisionResult,
        star_result: DecisionResult | None = None,
    ) -> RouteDecision:
        assert star_result is not None
        return RouteDecision(
            route="plan_then_execute",
            strategy_name=self.__class__.__name__,
            macro_intent=intent_result.output,
            micro_intent=intent_result.choices.get("micro_intent"),
            requires_star_verification=True,
            maintain_context=(intent_result.output == "BOTH"),
            star_status=star_result.output,
            is_sufficient=star_result.is_sufficient,
            missing_required=star_result.missing_required,
            reason="Minimum S and T threshold met; select implementation plan and verification.",
        )


class ClarifyParametersStrategy(RoutingStrategy):
    """Strategy when prompt is structured but missing S or T (CLARIFY_PARAMETERS)."""

    def build_decision(
        self,
        intent_result: DecisionResult,
        star_result: DecisionResult | None = None,
    ) -> RouteDecision:
        assert star_result is not None
        missing_str = ", ".join(star_result.missing_required)
        return RouteDecision(
            route="clarify_missing_parameters",
            strategy_name=self.__class__.__name__,
            macro_intent=intent_result.output,
            micro_intent=intent_result.choices.get("micro_intent"),
            requires_star_verification=True,
            maintain_context=(intent_result.output == "BOTH"),
            star_status=star_result.output,
            is_sufficient=star_result.is_sufficient,
            missing_required=star_result.missing_required,
            reason=f"Prompt is structured but missing required STAR parameter(s): {missing_str}.",
        )


class ScaffoldingPersonaStrategy(RoutingStrategy):
    """Strategy when prompt is vague/unstructured and missing S or T (SCAFFOLD_USER)."""

    def build_decision(
        self,
        intent_result: DecisionResult,
        star_result: DecisionResult | None = None,
    ) -> RouteDecision:
        assert star_result is not None
        missing_str = ", ".join(star_result.missing_required)
        return RouteDecision(
            route="switch_to_scaffolding_persona",
            strategy_name=self.__class__.__name__,
            macro_intent=intent_result.output,
            micro_intent=intent_result.choices.get("micro_intent"),
            requires_star_verification=True,
            maintain_context=(intent_result.output == "BOTH"),
            star_status=star_result.output,
            is_sufficient=star_result.is_sufficient,
            missing_required=star_result.missing_required,
            reason=f"Prompt is vague/unstructured and missing required STAR parameter(s): {missing_str}.",
        )


class ConversationRouter:
    """Routes dialogue segments using strategies keyed on Decider outputs."""

    STAR_STRATEGIES: dict[str, RoutingStrategy] = {
        "COMPLETE_STAR": DirectExecuteStrategy(),
        "MISSING_RESULT": ConfirmCriteriaStrategy(),
        "MISSING_ACTION": ProposeActionPlanStrategy(),
        "MINIMUM_SUFFICIENT": PlanThenExecuteStrategy(),
        "CLARIFY_PARAMETERS": ClarifyParametersStrategy(),
        "SCAFFOLD_USER": ScaffoldingPersonaStrategy(),
    }

    def __init__(self, manager: DeciderManager | None = None) -> None:
        self.manager = manager
        self.context_strategy = ContextMaintenanceStrategy()
        self.validation_strategy = LightweightValidationStrategy()
        self.fallback_strategy = AmbiguousFallbackStrategy()

    def route_from_intent(self, intent_result: DecisionResult) -> RouteDecision:
        """Select and apply the intent-stage strategy (before or without STAR evaluation)."""
        macro = intent_result.output
        micro = intent_result.choices.get("micro_intent")

        if macro == "AMBIGUOUS":
            return self.fallback_strategy.build_decision(intent_result)

        if macro == "INFORM":
            return self.context_strategy.build_decision(intent_result)

        if micro in ("confirm_understanding", "validate_info"):
            return self.validation_strategy.build_decision(intent_result)

        # Actionable PERSUADE / BOTH turn that requires STAR evaluation
        return RouteDecision(
            route=f"execute_{micro}" if micro else "execute_task",
            strategy_name="PendingStarVerification",
            macro_intent=macro,
            micro_intent=micro,
            requires_star_verification=True,
            maintain_context=(macro == "BOTH"),
            reason=f"Macro intent is {macro}; requires STAR decider verification.",
        )

    def route_from_star(
        self,
        star_result: DecisionResult,
        intent_result: DecisionResult | None = None,
    ) -> RouteDecision:
        """Select and apply the STAR-stage strategy from a STAR DecisionResult."""
        synthetic_intent = intent_result or DecisionResult(
            decider_name="intent",
            output="PERSUADE",
            booleans={"is_inform": False, "is_persuade": True},
            probabilities={"is_inform": 0.0, "is_persuade": 1.0},
            choices={"micro_intent": None},
        )
        strategy = self.STAR_STRATEGIES[star_result.output]
        return strategy.build_decision(intent_result=synthetic_intent, star_result=star_result)

    def route_state(self, state: dict[str, Any]) -> tuple[RouteDecision, DecisionResult, DecisionResult | None]:
        """End-to-end routing: run intent decider first, then STAR decider if required."""
        if self.manager is None:
            raise ValueError("ConversationRouter requires a JevManager to run route_state().")

        intent_result = self.manager.decide("intent", state)
        initial_decision = self.route_from_intent(intent_result)

        if not initial_decision.requires_star_verification:
            return initial_decision, intent_result, None

        star_result = self.manager.decide("star", state)
        final_decision = self.route_from_star(star_result=star_result, intent_result=intent_result)
        return final_decision, intent_result, star_result
