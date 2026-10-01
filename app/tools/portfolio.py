"""getUserPortfolio(userId) - holdings, active SIPs and wallet balance."""

from __future__ import annotations

from typing import Any, Dict

from ..data.users import get_user
from ..models import Card, Chip, ToolResult


def _money(value: float) -> str:
    """Indian grouping: 12,34,567.89 rather than 1,234,567.89."""
    negative = value < 0
    whole, _, frac = ("%.2f" % abs(value)).partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return "%s₹%s.%s" % ("-" if negative else "", whole, frac)


def get_user_portfolio(user_id: str) -> ToolResult:
    user = get_user(user_id)

    holdings = []
    equity_invested = equity_value = 0.0
    for h in user["holdings"]:
        invested = h["qty"] * h["avg_price"]
        value = h["qty"] * h["last_price"]
        equity_invested += invested
        equity_value += value
        holdings.append({
            "symbol": h["symbol"],
            "name": h["name"],
            "qty": h["qty"],
            "avg_price": h["avg_price"],
            "last_price": h["last_price"],
            "invested": round(invested, 2),
            "value": round(value, 2),
            "pnl": round(value - invested, 2),
            "pnl_pct": round((value - invested) / invested * 100, 2) if invested else 0.0,
        })

    sips = []
    sip_invested = sip_value = 0.0
    for s in user["sips"]:
        sip_invested += s["invested"]
        sip_value += s["current_value"]
        sips.append({
            "sip_id": s["sip_id"],
            "scheme": s["scheme"],
            "amount": s["amount"],
            "frequency": s["frequency"],
            "next_debit": s["next_debit"],
            "instalments_done": s["instalments_done"],
            "invested": s["invested"],
            "current_value": s["current_value"],
            "pnl": round(s["current_value"] - s["invested"], 2),
            "status": s["status"],
        })

    invested = equity_invested + sip_invested
    value = equity_value + sip_value
    pnl = value - invested

    data: Dict[str, Any] = {
        "name": user["name"],
        "wallet_balance": user["wallet_balance"],
        "kyc_status": user["kyc_status"],
        "totals": {
            "invested": round(invested, 2),
            "value": round(value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl / invested * 100, 2) if invested else 0.0,
        },
        "holdings": holdings,
        "sips": sips,
    }

    active = [s for s in sips if s["status"] == "active"]
    if holdings:
        summary = ("You're holding %d stocks and %d SIP%s. Everything together is "
                   "worth %s right now." % (len(holdings), len(sips),
                                            "" if len(sips) == 1 else "s",
                                            _money(value)))
    elif sips:
        summary = ("You have %d active SIP%s. %s invested so far, worth %s today."
                   % (len(active), "" if len(active) == 1 else "s",
                      _money(sip_invested), _money(sip_value)))
    else:
        summary = ("Nothing invested yet — your wallet has %s ready to go."
                   % _money(user["wallet_balance"]))

    chips = [Chip("Check SIP status", "What is the status of my SIP?")]
    if holdings:
        chips.append(Chip("Understand my P&L", "Explain my P&L and STCG"))
    chips.append(Chip("Track a withdrawal", "Track my withdrawal"))

    return ToolResult(
        text=summary,
        cards=[Card(kind="portfolio", data=data)],
        chips=chips,
        raw=data,
    )
