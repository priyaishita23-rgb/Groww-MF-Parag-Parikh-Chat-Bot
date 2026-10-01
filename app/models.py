"""Shared types for the assistant.

The contract between the agent and the UI is deliberately narrow: a turn
produces some text, zero or more **cards**, and zero or more **chips**. The
browser knows how to render each card `kind` and nothing else, so adding a
capability means adding a tool and a card renderer, not touching the agent.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional

Role = Literal["user", "assistant"]

#: Every card kind the browser can draw. Anything else is a bug, not a
#: fallback - a card the UI cannot render would silently vanish from a reply.
CardKind = Literal[
    "portfolio",     # holdings, SIPs, wallet
    "order_status",  # stepper
    "sip_projection",  # calculator result
    "ticket",        # support ticket receipt
    "disclaimer",    # compliance notice
]


@dataclass
class Card:
    kind: CardKind
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "data": self.data}


@dataclass
class Chip:
    """A quick-reply suggestion. `send` is what gets submitted when tapped."""

    label: str
    send: str

    def to_dict(self) -> Dict[str, Any]:
        return {"label": self.label, "send": self.send}


@dataclass
class Message:
    role: Role
    text: str
    cards: List[Card] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "cards": [c.to_dict() for c in self.cards],
        }


@dataclass
class Reply:
    """One assistant turn, before it is streamed to the browser."""

    text: str
    cards: List[Card] = field(default_factory=list)
    chips: List[Chip] = field(default_factory=list)
    #: Which tool ran, for the trace panel and the tests. None when the turn
    #: was settled by a guardrail before any tool was considered.
    tool: Optional[str] = None
    #: Set when a compliance rule shaped the reply, so it can be asserted on.
    guardrail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "cards": [c.to_dict() for c in self.cards],
            "chips": [c.to_dict() for c in self.chips],
            "tool": self.tool,
            "guardrail": self.guardrail,
        }


@dataclass
class ToolResult:
    """What a mock domain tool hands back to the agent."""

    text: str
    cards: List[Card] = field(default_factory=list)
    chips: List[Chip] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)
