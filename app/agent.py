"""The agent: guardrails, then a tool, then a reply.

    message -> guardrails -> tool selection -> tool -> Reply(text, cards, chips)

**Guardrails run first and can end the turn.** Distress escalates before
anything else is considered; advisory questions are declined before a tool
could dress one up as an answer. Nothing downstream can overturn them.

**Tool selection is deterministic.** Intent is matched on patterns, not
inferred by a model. For a support surface where the wrong branch means a
frozen-account report is answered with an FAQ link, predictable beats clever,
and every route here is covered by a test. `SCHEMAS` in `tools/__init__.py`
exposes the same tools in function-calling shape, so a model-driven planner
can be dropped in later without the tools or the guardrails changing.
"""

from __future__ import annotations

import re
from typing import List, Optional

from . import guardrails
from .data.users import get_user
from .models import Card, Chip, Reply
from .tools import (
    calculate_returns,
    escalate_to_human_agent,
    extract_order_id,
    get_transaction_status,
    get_user_portfolio,
    list_recent_orders,
    parse_request,
    ticket_status,
)

_TICKET = re.compile(r"\b(GRW-[0-9A-F]{6})\b", re.I)

_PORTFOLIO = re.compile(
    r"\b(portfolio|holdings?|my (stocks?|shares?|investments?|funds?)|"
    r"what do i (own|hold)|wallet|balance|how much (have i|did i) invest|"
    r"my p&?l|profit (and|&) loss|my returns?|how (am i|are my investments) doing)\b",
    re.I,
)
_SIP_STATUS = re.compile(
    r"\b(sip (status|update|running|active|deducted|debited)|"
    r"my sips?\b|status of my sip|is my sip|sip not|next (sip|instal)\w*)\b", re.I)
# Note the `\d+` rather than `\d`. With a single `\d` the group's closing `\b`
# lands between the first digit and the second - no boundary there - so
# "SIP of 5000" silently failed to match while "SIP of 5" worked.
_CALCULATOR = re.compile(
    r"\b(calculat\w+|project\w+|illustrat\w+|what (would|will) .{0,20}(grow|become)|"
    r"if i invest|sip of \d+|invest \d+ (a|per) month|per month for \d+|corpus|"
    r"how much .{0,20}in \d+\s*years?)\b",
    re.I,
)
_ORDERS = re.compile(r"\b(my (recent )?orders?|order history|show my orders)\b", re.I)
_TRACK = re.compile(
    r"\b(track|status of|where is|what.?s happening (with|to))\b.{0,30}"
    r"\b(order|withdrawal|deposit|payment|redemption|transaction)\b", re.I)
_WITHDRAWAL = re.compile(r"\b(withdraw\w*|payout|redemption|redeem)\b", re.I)
_STCG = re.compile(r"\b(stcg|ltcg|capital gains?|tax on (my )?(gains?|profit))\b", re.I)
_TPLUS2 = re.compile(r"\b(t\+?2|why .{0,25}(allotment|units).{0,15}(take|delay)|"
                     r"when will .{0,15}units)\b", re.I)
_HUMAN = re.compile(
    r"\b(raise a ticket|open a ticket|create a ticket|speak to (a|an) (human|agent|person)|"
    r"talk to (a|an) (human|agent|person)|human agent|customer care|call me|"
    r"escalate|complaint|contact support)\b", re.I)
_GREETING = re.compile(r"^\s*(hi|hey|hello|yo|good (morning|afternoon|evening))\b", re.I)


def default_chips() -> List[Chip]:
    return [
        Chip("Check SIP status", "What is the status of my SIP?"),
        Chip("Track withdrawal", "Track my withdrawal"),
        Chip("Understand P&L / STCG", "Explain my P&L and STCG"),
        Chip("Raise a ticket", "I want to raise a ticket"),
    ]


def _first_order_of_type(user_id: str, pattern: re.Pattern) -> Optional[str]:
    user = get_user(user_id)
    for order_id, order in user["orders"].items():
        if pattern.search(order["type"]):
            return order_id
    return None


def respond(message: str, session_id: str, user_id: str) -> Reply:
    text = (message or "").strip()
    user = get_user(user_id)

    if not text:
        return Reply(text="What can I help you with?", chips=default_chips())

    # ---- 1. guardrails, before anything else --------------------------------
    verdict = guardrails.check(text)

    if verdict and verdict.family == "distress":
        # Escalate first, ask questions later. Someone whose money is missing
        # should not be routed through self-service.
        result = escalate_to_human_agent(
            session_id=session_id,
            user_id=user_id,
            user_name=user["name"],
            message=text,
            order_id=extract_order_id(text),
        )
        return Reply(text=result.text, cards=result.cards, chips=result.chips,
                     tool="escalateToHumanAgent", guardrail="distress")

    if verdict and verdict.family == "advisory":
        symbol = guardrails.extract_symbol(text)
        card = Card(kind="disclaimer", data={
            "title": "I can't give investment advice",
            "body": guardrails.ADVISORY_DISCLAIMER,
            "subject": symbol,
            "alternatives": [
                "Fundamentals, price history and charts on the instrument page",
                "The scheme's own factsheet and risk disclosures",
                "Your own holdings and P&L, which I can pull up now",
            ],
        })
        chips = [Chip("Show my portfolio", "Show my portfolio"),
                 Chip("Run a SIP illustration", "Calculate a SIP of 5000 for 10 years at 12%")]
        if symbol:
            chips.insert(0, Chip("%s fundamentals" % symbol,
                                 "Where can I see %s fundamentals?" % symbol))
        opener = ("I can't tell you whether to buy or sell %s."
                  % symbol if symbol else "I can't tell you what to buy or sell.")
        return Reply(text=opener, cards=[card], chips=chips, guardrail="advisory")

    if verdict and verdict.family == "projection":
        amount, years, rate = parse_request(text)
        result = calculate_returns(amount, years, rate)
        card = Card(kind="disclaimer", data={
            "title": "No returns are guaranteed",
            "body": guardrails.PROJECTION_DISCLAIMER,
            "subject": None,
            "alternatives": [],
        })
        return Reply(text=result.text, cards=[card] + result.cards,
                     chips=result.chips, tool="calculateReturns",
                     guardrail="projection")

    # ---- 2. explicit hand-off request ---------------------------------------
    if _HUMAN.search(text):
        result = escalate_to_human_agent(
            session_id=session_id, user_id=user_id, user_name=user["name"],
            message=text, order_id=extract_order_id(text))
        return Reply(text=result.text, cards=result.cards, chips=result.chips,
                     tool="escalateToHumanAgent")

    found_ticket = _TICKET.search(text)
    if found_ticket:
        result = ticket_status(found_ticket.group(1))
        return Reply(text=result.text, cards=result.cards, chips=result.chips,
                     tool="ticketStatus")

    # ---- 3. tools ------------------------------------------------------------
    order_id = extract_order_id(text)
    if order_id:
        result = get_transaction_status(order_id)
        return Reply(text=result.text, cards=result.cards, chips=result.chips,
                     tool="getTransactionStatus")

    if _CALCULATOR.search(text):
        amount, years, rate = parse_request(text)
        result = calculate_returns(amount, years, rate)
        return Reply(text=result.text, cards=result.cards, chips=result.chips,
                     tool="calculateReturns")

    if _ORDERS.search(text):
        result = list_recent_orders(user_id)
        return Reply(text=result.text, cards=result.cards, chips=result.chips,
                     tool="listRecentOrders")

    if _TRACK.search(text) or (_WITHDRAWAL.search(text) and "sip" not in text.lower()):
        found = _first_order_of_type(user_id, re.compile(r"withdraw", re.I))
        if found:
            result = get_transaction_status(found)
            return Reply(text=result.text, cards=result.cards, chips=result.chips,
                         tool="getTransactionStatus")
        return Reply(
            text=("I can't see a withdrawal on this account. If you have the order "
                  "reference (it looks like ORD-77190) paste it and I'll track it."),
            chips=[Chip("Show my orders", "Show my recent orders")])

    if _SIP_STATUS.search(text):
        sips = user["sips"]
        if not sips:
            return Reply(
                text=("You don't have a SIP running yet. When you start one it'll "
                      "show up here with its next debit date."),
                chips=[Chip("Run an illustration",
                            "Calculate a SIP of 5000 for 10 years at 12%")])
        pending = _first_order_of_type(user_id, re.compile(r"SIP", re.I))
        if pending:
            result = get_transaction_status(pending)
            return Reply(text=result.text, cards=result.cards, chips=result.chips,
                         tool="getTransactionStatus")
        result = get_user_portfolio(user_id)
        return Reply(text=result.text, cards=result.cards, chips=result.chips,
                     tool="getUserPortfolio")

    if _TPLUS2.search(text):
        return Reply(
            text=("Mutual fund units aren't allotted instantly. The money leaves on "
                  "the SIP date, reaches the AMC the same day, and the AMC allots "
                  "units at the applicable NAV — usually two working days later. "
                  "Your money is invested from the debit date; only the unit count "
                  "shows up later."),
            chips=[Chip("Track my SIP order", "What is the status of my SIP?"),
                   Chip("Show my portfolio", "Show my portfolio")])

    if _STCG.search(text):
        return Reply(
            text=("Short-term capital gains apply when you sell equity held for a "
                  "year or less, and are taxed at a flat rate; hold longer and "
                  "long-term rates with an annual exemption apply instead. Your "
                  "realised gains and the tax already reported sit in the tax "
                  "statement on your account — I can show your current unrealised "
                  "P&L here, but the statement is what you'd file from."),
            cards=get_user_portfolio(user_id).cards,
            chips=[Chip("Show my portfolio", "Show my portfolio"),
                   Chip("Raise a ticket", "I want to raise a ticket about my tax statement")],
            tool="getUserPortfolio")

    if _PORTFOLIO.search(text):
        result = get_user_portfolio(user_id)
        return Reply(text=result.text, cards=result.cards, chips=result.chips,
                     tool="getUserPortfolio")

    if _GREETING.search(text):
        return Reply(
            text=("Hi %s. I can check your portfolio, track an order or a "
                  "withdrawal, run a SIP illustration, or put you through to a "
                  "person. What's up?" % user["name"].split()[0]),
            chips=default_chips())

    # ---- 4. nothing matched --------------------------------------------------
    return Reply(
        text=("I'm not sure I followed that. I can look up your portfolio, track an "
              "order, illustrate a SIP, or raise a ticket with a human — which "
              "of those is closest?"),
        chips=default_chips())
