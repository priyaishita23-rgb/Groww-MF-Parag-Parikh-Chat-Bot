"""The mock domain tools, and their machine-readable schemas.

SCHEMAS is the structured tool-calling contract. It is shaped like an
OpenAI/Gemini function-calling declaration so the agent can hand it to a model
unchanged, and the deterministic router uses the same names, so both paths
call exactly the same code.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .escalation import escalate_to_human_agent, ticket_status
from .portfolio import get_user_portfolio
from .returns import calculate_returns, parse_request
from .transactions import extract_order_id, get_transaction_status, list_recent_orders

SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "getUserPortfolio",
        "description": ("Holdings, active SIPs and wallet balance for the signed-in "
                        "user. Use for any question about what they own, how much "
                        "they have invested, or their profit and loss."),
        "parameters": {
            "type": "object",
            "properties": {
                "userId": {"type": "string", "description": "The signed-in user's id"}
            },
            "required": ["userId"],
        },
    },
    {
        "name": "getTransactionStatus",
        "description": ("Where a specific order has got to: SIP instalments, "
                        "withdrawals, deposits. Needs the order reference."),
        "parameters": {
            "type": "object",
            "properties": {
                "orderId": {"type": "string", "description": "e.g. ORD-88213"}
            },
            "required": ["orderId"],
        },
    },
    {
        "name": "calculateReturns",
        "description": ("Illustrate what a monthly SIP would grow to at an assumed "
                        "rate. Arithmetic only - never present it as a forecast."),
        "parameters": {
            "type": "object",
            "properties": {
                "sipAmount": {"type": "number", "description": "Monthly amount in rupees"},
                "tenureYears": {"type": "number", "description": "Years to run"},
                "expectedRate": {"type": "number", "description": "Assumed annual %"},
            },
            "required": ["sipAmount", "tenureYears", "expectedRate"],
        },
    },
    {
        "name": "escalateToHumanAgent",
        "description": ("Open a support ticket and hand to a human. Use immediately "
                        "for uncredited funds, failed deposits, a frozen account or "
                        "unauthorised activity - do not troubleshoot those first."),
        "parameters": {
            "type": "object",
            "properties": {
                "issue": {"type": "string", "description": "What the user reported"},
                "orderId": {"type": "string", "description": "Related order, if any"},
            },
            "required": ["issue"],
        },
    },
]

__all__ = [
    "SCHEMAS",
    "get_user_portfolio",
    "get_transaction_status",
    "list_recent_orders",
    "extract_order_id",
    "calculate_returns",
    "parse_request",
    "escalate_to_human_agent",
    "ticket_status",
]
