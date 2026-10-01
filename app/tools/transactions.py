"""getTransactionStatus(orderId) - where an order actually is, as a stepper."""

from __future__ import annotations

import re
from typing import Optional

from ..data.users import find_order, get_user
from ..models import Card, Chip, ToolResult

ORDER_PATTERN = re.compile(r"\b(ORD[- ]?\d{4,6})\b", re.I)


def extract_order_id(message: str) -> Optional[str]:
    found = ORDER_PATTERN.search(message or "")
    if not found:
        return None
    return found.group(1).upper().replace(" ", "-")


def get_transaction_status(order_id: str) -> ToolResult:
    match = find_order(order_id)
    if match is None:
        return ToolResult(
            text=("I couldn't find an order with that reference. Order IDs look "
                  "like ORD-88213 — you'll find yours on the order's detail "
                  "page. Paste it here and I'll track it."),
            chips=[Chip("Show my orders", "Show my recent orders")],
        )

    _user, order = match
    data = {
        "order_id": order["order_id"],
        "type": order["type"],
        "amount": order["amount"],
        "placed_on": order["placed_on"],
        "status_code": order["status_code"],
        "headline": order["headline"],
        "detail": order["detail"],
        "steps": order["steps"],
        "scheme": order.get("scheme"),
        "utr": order.get("utr"),
    }

    chips = [Chip("Raise a ticket", "I want to raise a ticket about %s" % order["order_id"])]
    if order["status_code"] == "units_pending":
        chips.insert(0, Chip("Why T+2?", "Why does unit allotment take T+2 days?"))
    if order["status_code"] == "failed":
        chips.insert(0, Chip("Get this refunded", "My deposit failed and money was debited"))

    return ToolResult(
        text="%s — %s" % (order["order_id"], order["headline"]),
        cards=[Card(kind="order_status", data=data)],
        chips=chips,
        raw=data,
    )


def list_recent_orders(user_id: str) -> ToolResult:
    """Not one of the four required tools, but a question people always ask."""
    user = get_user(user_id)
    orders = list(user["orders"].values())
    if not orders:
        return ToolResult(text="You don't have any orders on this account yet.")

    lines = ["Here's what's on your account:"]
    chips = []
    for order in orders:
        lines.append("• %s — %s" % (order["order_id"], order["headline"]))
        chips.append(Chip(order["order_id"], "Track order %s" % order["order_id"]))
    return ToolResult(text="\n".join(lines), chips=chips[:3])
