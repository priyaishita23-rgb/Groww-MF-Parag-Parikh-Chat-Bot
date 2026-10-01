"""Two mock investor profiles, and the orders attached to them.

Deterministic on purpose. Every number here is fixed, so a demo gives the same
answer twice and a test can assert on it. Nothing is randomised and no value
is computed from today's date.

  U1001  Ananya  - new investor, one active SIP, small wallet, no equity
  U2002  Vikram  - active equity trader, several holdings, two SIPs, a failed
                   deposit that exists specifically to exercise escalation
"""

from __future__ import annotations

from typing import Any, Dict, List

USERS: Dict[str, Dict[str, Any]] = {
    "U1001": {
        "user_id": "U1001",
        "name": "Ananya Rao",
        "persona": "new investor",
        "joined": "2026-06-14",
        "wallet_balance": 2450.00,
        "kyc_status": "verified",
        "holdings": [],
        "sips": [
            {
                "sip_id": "SIP-4417",
                "scheme": "Parag Parikh Flexi Cap Fund - Direct Growth",
                "amount": 2000,
                "frequency": "monthly",
                "next_debit": "2026-10-05",
                "started": "2026-07-05",
                "instalments_done": 3,
                "invested": 6000.00,
                "current_value": 6284.40,
                "status": "active",
            }
        ],
        "orders": {
            "ORD-88213": {
                "order_id": "ORD-88213",
                "type": "SIP instalment",
                "scheme": "Parag Parikh Flexi Cap Fund - Direct Growth",
                "amount": 2000,
                "placed_on": "2026-09-05",
                "status_code": "units_pending",
                "headline": "SIP deducted, units allotment pending by AMC",
                "detail": "The AMC allots units on a T+2 basis. Your units should "
                          "appear by 9 September 2026.",
                "steps": [
                    {"label": "Mandate debited", "state": "done", "at": "05 Sep, 08:12"},
                    {"label": "Funds sent to AMC", "state": "done", "at": "05 Sep, 14:40"},
                    {"label": "Units allotted", "state": "active", "at": "expected 09 Sep"},
                    {"label": "Reflected in portfolio", "state": "todo", "at": ""},
                ],
            }
        },
    },
    "U2002": {
        "user_id": "U2002",
        "name": "Vikram Shetty",
        "persona": "active equity trader",
        "joined": "2023-02-02",
        "wallet_balance": 18730.55,
        "kyc_status": "verified",
        "holdings": [
            {"symbol": "TATAMOTORS", "name": "Tata Motors", "qty": 120,
             "avg_price": 742.10, "last_price": 806.45},
            {"symbol": "INFY", "name": "Infosys", "qty": 45,
             "avg_price": 1512.00, "last_price": 1468.30},
            {"symbol": "HDFCBANK", "name": "HDFC Bank", "qty": 60,
             "avg_price": 1602.75, "last_price": 1711.20},
            {"symbol": "ITC", "name": "ITC", "qty": 200,
             "avg_price": 412.60, "last_price": 421.05},
        ],
        "sips": [
            {
                "sip_id": "SIP-1188",
                "scheme": "Nifty 50 Index Fund - Direct Growth",
                "amount": 10000,
                "frequency": "monthly",
                "next_debit": "2026-10-01",
                "started": "2024-01-01",
                "instalments_done": 33,
                "invested": 330000.00,
                "current_value": 391642.80,
                "status": "active",
            },
            {
                "sip_id": "SIP-2291",
                "scheme": "Mid Cap Opportunities Fund - Direct Growth",
                "amount": 5000,
                "frequency": "monthly",
                "next_debit": "2026-10-10",
                "started": "2025-04-10",
                "instalments_done": 18,
                "invested": 90000.00,
                "current_value": 97355.00,
                "status": "paused",
            },
        ],
        "orders": {
            "ORD-77190": {
                "order_id": "ORD-77190",
                "type": "Withdrawal to bank",
                "amount": 25000,
                "placed_on": "2026-09-27",
                "status_code": "bank_processing",
                "headline": "Withdrawal sent to your bank, awaiting credit",
                "detail": "Redemption is complete and the payout has left us. Banks "
                          "usually credit within 24 working hours; the UTR is "
                          "available below if your bank asks for it.",
                "utr": "UTR2026092700419",
                "steps": [
                    {"label": "Redemption placed", "state": "done", "at": "27 Sep, 10:02"},
                    {"label": "Units redeemed", "state": "done", "at": "27 Sep, 16:30"},
                    {"label": "Payout initiated", "state": "done", "at": "28 Sep, 09:15"},
                    {"label": "Credited to bank", "state": "active", "at": "in progress"},
                ],
            },
            "ORD-77455": {
                "order_id": "ORD-77455",
                "type": "Deposit via UPI",
                "amount": 50000,
                "placed_on": "2026-09-29",
                "status_code": "failed",
                "headline": "Deposit failed, amount debited by your bank",
                "detail": "The payment did not reach us but your bank has debited it. "
                          "This is an auto-reversal case and needs a human to chase "
                          "the payment partner.",
                "steps": [
                    {"label": "Payment initiated", "state": "done", "at": "29 Sep, 11:41"},
                    {"label": "Bank debited", "state": "done", "at": "29 Sep, 11:41"},
                    {"label": "Credited to wallet", "state": "failed", "at": "failed"},
                ],
            },
        },
    },
}

#: The profile a fresh session starts on.
DEFAULT_USER_ID = "U1001"


def get_user(user_id: str) -> Dict[str, Any]:
    return USERS.get(user_id) or USERS[DEFAULT_USER_ID]


def list_users() -> List[Dict[str, str]]:
    return [
        {"user_id": u["user_id"], "name": u["name"], "persona": u["persona"]}
        for u in USERS.values()
    ]


def find_order(order_id: str):
    """Look an order up across every profile; returns (user, order) or None."""
    wanted = (order_id or "").strip().upper()
    for user in USERS.values():
        for oid, order in user["orders"].items():
            if oid.upper() == wanted:
                return user, order
    return None
