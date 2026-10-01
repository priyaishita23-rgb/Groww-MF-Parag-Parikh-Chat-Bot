"""escalateToHumanAgent(ticketData) - open a ticket and hand over.

Ticket IDs are deterministic: the same session raising the same issue gets the
same ID rather than a new one on every retry. A support bot that mints a fresh
ticket each time someone rephrases is how a single problem becomes five open
tickets and nobody owns any of them.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from ..models import Card, Chip, ToolResult

#: Issue categories, ordered by how badly a delay hurts. Money that has left
#: someone's bank and not arrived outranks a question about paperwork.
CATEGORIES: List[Dict[str, Any]] = [
    {
        "key": "unauthorised_activity",
        "label": "Unauthorised activity",
        "priority": "P0",
        "score": 98,
        "sla_hours": 2,
        "team": "Fraud & Risk",
        "keywords": ["unauthori", "fraud", "hacked", "stolen", "someone else",
                     "did not place", "didn't place", "did not authorise"],
    },
    {
        "key": "account_access",
        "label": "Account frozen or blocked",
        "priority": "P0",
        "score": 95,
        "sla_hours": 3,
        "team": "Account Operations",
        "keywords": ["frozen", "blocked", "locked", "suspended", "restricted",
                     "cannot log in", "can't log in", "cannot access"],
    },
    {
        "key": "funds_not_credited",
        "label": "Funds debited but not credited",
        "priority": "P1",
        "score": 90,
        "sla_hours": 4,
        "team": "Payments",
        "keywords": ["not credited", "uncredited", "debited but", "deducted but",
                     "failed deposit", "deposit failed", "payment failed",
                     "missing money", "missing funds", "where is my money"],
    },
    {
        "key": "withdrawal_delay",
        "label": "Withdrawal delayed",
        "priority": "P2",
        "score": 70,
        "sla_hours": 12,
        "team": "Payments",
        "keywords": ["withdrawal", "payout", "redemption", "not received"],
    },
    {
        "key": "order_issue",
        "label": "Order or allotment issue",
        "priority": "P2",
        "score": 60,
        "sla_hours": 24,
        "team": "Orders",
        "keywords": ["order", "sip", "allotment", "units", "nav"],
    },
    {
        "key": "general",
        "label": "General support",
        "priority": "P3",
        "score": 30,
        "sla_hours": 48,
        "team": "Support",
        "keywords": [],
    },
]


def classify(message: str) -> Dict[str, Any]:
    text = (message or "").lower()
    for category in CATEGORIES:
        for keyword in category["keywords"]:
            if keyword in text:
                return category
    return CATEGORIES[-1]


def _ticket_id(session_id: str, category_key: str) -> str:
    """Stable per (session, issue) so a retry reuses the same ticket."""
    digest = hashlib.sha256(("%s|%s" % (session_id, category_key)).encode()).hexdigest()
    return "GRW-%s" % digest[:6].upper()


def escalate_to_human_agent(
    session_id: str,
    user_id: str,
    user_name: str,
    message: str,
    order_id: Optional[str] = None,
) -> ToolResult:
    category = classify(message)
    ticket_id = _ticket_id(session_id, category["key"])

    data: Dict[str, Any] = {
        "ticket_id": ticket_id,
        "category": category["label"],
        "priority": category["priority"],
        "priority_score": category["score"],
        "sla_hours": category["sla_hours"],
        "team": category["team"],
        "raised_for": user_name,
        "user_id": user_id,
        "order_id": order_id,
        "summary": (message or "").strip()[:180],
        "channel": "Chat",
        "next_update": "within %d hours" % category["sla_hours"],
    }

    if category["priority"] in ("P0", "P1"):
        opener = ("That shouldn't happen, and it's not something you should have "
                  "to chase. I've put this straight through to our %s team."
                  % category["team"])
    else:
        opener = "I've raised this with our %s team for you." % category["team"]

    text = ("%s Your reference is %s and someone will come back to you %s. "
            "You don't need to do anything else in the meantime."
            % (opener, ticket_id, data["next_update"]))

    return ToolResult(
        text=text,
        cards=[Card(kind="ticket", data=data)],
        chips=[
            Chip("Check ticket status", "What is the status of ticket %s?" % ticket_id),
            Chip("Add more detail", "I want to add details to %s" % ticket_id),
        ],
        raw=data,
    )


def ticket_status(ticket_id: str) -> ToolResult:
    """Look-up for a ticket the assistant raised earlier in the session."""
    return ToolResult(
        text=("Ticket %s is open and with the team. You'll get an update by email "
              "and here in chat as soon as there's news — there's nothing "
              "further you need to do." % ticket_id.upper()),
        chips=[Chip("Something else", "I need help with something else")],
    )
