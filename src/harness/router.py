"""Conversation router."""

from dataclasses import dataclass

from src.harness.evaluator import IntentEvaluation


@dataclass(frozen=True)
class RouteDecision:
    """Routing decision produced from an IntentEvaluation."""

    route: str
    macro_intent: str
    micro_intent: str | None
    requires_star_verification: bool
    reason: str


class IntentRouter:
    """Truth-table router mapping calibrated intent judgments to handler routes."""

    def route_intent(self, evaluation: IntentEvaluation) -> RouteDecision:
        """Map Macro and Operational Micro Intents to a deterministic route."""
        macro = evaluation.macro_intent
        micro = evaluation.micro_intent

        # 1. No recognizable operational micro intent and ambiguous macro intent
        if macro == "AMBIGUOUS" and micro is None:
            return RouteDecision(
                route="clarify_or_acknowledge",
                macro_intent=macro,
                micro_intent=micro,
                requires_star_verification=False,
                reason="Neither inform nor persuade crossed the 0.7 threshold and no micro intent matched.",
            )

        # 2. Pure INFORM turn (e.g., provide_update, clarify_point without command)
        if macro == "INFORM":
            route_name = f"ingest_{micro}" if micro else "ingest_context"
            return RouteDecision(
                route=route_name,
                macro_intent=macro,
                micro_intent=micro,
                requires_star_verification=False,
                reason="User is providing context or updates without requesting task execution.",
            )

        # 3. PERSUADE or BOTH: actionable turn -> requires STAR completeness check for task execution
        if macro in ("PERSUADE", "BOTH"):
            # Lightweight informational/validation checks vs full task execution
            if micro in ("confirm_understanding", "validate_info"):
                return RouteDecision(
                    route=f"handle_{micro}",
                    macro_intent=macro,
                    micro_intent=micro,
                    requires_star_verification=False,
                    reason=f"Actionable {micro} check on existing context.",
                )
            return RouteDecision(
                route=f"execute_{micro}" if micro else "execute_task",
                macro_intent=macro,
                micro_intent=micro,
                requires_star_verification=True,
                reason=f"Macro intent is {macro}; segment requires STAR verification before execution.",
            )

        # 4. Fallback for AMBIGUOUS macro with a detected micro intent
        return RouteDecision(
            route=f"fallback_{micro}",
            macro_intent=macro,
            micro_intent=micro,
            requires_star_verification=False,
            reason="Macro intent landed in the uncertain band; routing cautiously by micro intent.",
        )
