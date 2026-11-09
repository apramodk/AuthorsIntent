"""ConversationRouter entry point coordinating DeciderManager across segment, intent, and STAR schemas."""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from src.clients.base import DecisionClient
from src.clients.jevClient import JevClient
from src.deciders.deciderFactory import DecisionResult
from src.deciders.deciderManager import DeciderManager

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
LIGHTWEIGHT_MICRO_INTENTS = frozenset({"confirm_understanding", "validate_info"})


@dataclass(frozen=True)
class RouteDecision:
    """Routing decision produced by ConversationRouter from intent and optional STAR Decider results."""

    macro_intent: str
    micro_intent: str | None
    requires_star_verification: bool
    maintain_context: bool
    star_status: str | None = None
    is_sufficient: bool | None = None
    missing_required: list[str] | None = None


class ConversationRouter:
    """Main entry point managing deciders for topic segmentation, intent, and STAR verification."""

    def __init__(
        self,
        client: DecisionClient | None = None,
        manager: DeciderManager | None = None,
        schemas_dir: Path | None = None,
    ) -> None:
        if manager is not None:
            self.manager = manager
            self.client = manager.client
        else:
            self.client = client or JevClient()
            self.manager = DeciderManager(client=self.client, schemas_dir=schemas_dir)

    def decide(self, name: str, state: dict[str, Any]) -> DecisionResult:
        """Evaluate `state` against the named decider ('intent', 'star', 'segment', etc.)."""
        return self.manager.decide(name=name, state=state)

    def close(self) -> None:
        """Close the underlying client if it holds open resources."""
        close_fn = getattr(self.client, "close", None)
        if callable(close_fn):
            close_fn()

    @staticmethod
    def format_messages(messages: list[dict[str, str]]) -> str:
        """Format a contiguous list of OpenAI-style {role, content} messages into a single string."""
        return "\n".join(
            f"{m['role']}: {m['content'].strip()}"
            for m in messages
            if m.get("content", "").strip()
        )

    def segment_messages(
        self,
        messages: list[dict[str, str]],
        window_size: int = 2,
    ) -> list[list[dict[str, str]]]:
        """Group an OpenAI-style conversation thread into contiguous topic segments using the 'segment' decider."""
        if not messages:
            return []

        segments: list[list[dict[str, str]]] = [[dict(messages[0])]]

        for msg in messages[1:]:
            current_segment = segments[-1]
            context_window = current_segment[-window_size:] if window_size > 0 else current_segment
            result = self.decide(
                "segment",
                {"current_segment": context_window, "candidate_message": msg},
            )

            if result.output == "NEW_SEGMENT":
                segments.append([dict(msg)])
            elif result.output == "COMPOUND_SHIFT":
                sentences = [
                    s.strip() for s in SENTENCE_SPLIT_RE.split(msg["content"].strip()) if s.strip()
                ]
                if len(sentences) <= 1:
                    segments.append([dict(msg)])
                    continue

                role = msg["role"]
                split_occurred = False
                for sentence in sentences:
                    clause_msg = {"role": role, "content": sentence}
                    if not split_occurred:
                        clause_window = (
                            segments[-1][-window_size:] if window_size > 0 else segments[-1]
                        )
                        clause_res = self.decide(
                            "segment",
                            {"current_segment": clause_window, "candidate_message": clause_msg},
                        )
                        if clause_res.output in ("NEW_SEGMENT", "COMPOUND_SHIFT"):
                            segments.append([clause_msg])
                            split_occurred = True
                        else:
                            self._append_or_merge_role(segments[-1], clause_msg)
                    else:
                        self._append_or_merge_role(segments[-1], clause_msg)
            else:
                current_segment.append(dict(msg))

        return segments

    @staticmethod
    def _append_or_merge_role(segment: list[dict[str, str]], clause_msg: dict[str, str]) -> None:
        """Append a sentence clause or merge it into the last message if sent by the same role."""
        if segment and segment[-1]["role"] == clause_msg["role"]:
            segment[-1] = {
                "role": clause_msg["role"],
                "content": f"{segment[-1]['content']} {clause_msg['content']}".strip(),
            }
        else:
            segment.append(dict(clause_msg))

    def segment_thread(self, messages: list[dict[str, str]], window_size: int = 2) -> list[str]:
        """Segment an OpenAI-style conversation thread into a contiguous list of topic strings."""
        return [
            self.format_messages(group)
            for group in self.segment_messages(messages, window_size=window_size)
        ]

    @staticmethod
    def requires_star(intent_result: DecisionResult) -> bool:
        """Return True when an intent DecisionResult requires STAR completeness verification."""
        macro = intent_result.output
        micro = intent_result.choices.get("micro_intent")
        return macro in ("PERSUADE", "BOTH") and micro not in LIGHTWEIGHT_MICRO_INTENTS

    def route_state(
        self, state: dict[str, Any]
    ) -> tuple[RouteDecision, DecisionResult, DecisionResult | None]:
        """Run the 'intent' decider first, and conditionally run the 'star' decider when required."""
        intent_result = self.decide("intent", state)
        macro = intent_result.output
        micro = intent_result.choices.get("micro_intent")
        needs_star = self.requires_star(intent_result)

        if not needs_star:
            return (
                RouteDecision(
                    macro_intent=macro,
                    micro_intent=micro,
                    requires_star_verification=False,
                    maintain_context=macro in ("INFORM", "BOTH"),
                ),
                intent_result,
                None,
            )

        star_result = self.decide("star", state)
        return (
            RouteDecision(
                macro_intent=macro,
                micro_intent=micro,
                requires_star_verification=True,
                maintain_context=(macro == "BOTH"),
                star_status=star_result.output,
                is_sufficient=star_result.is_sufficient,
                missing_required=star_result.missing_required,
            ),
            intent_result,
            star_result,
        )
