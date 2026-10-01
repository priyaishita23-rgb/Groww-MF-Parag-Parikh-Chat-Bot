"""Compliance rules, evaluated before any tool is chosen.

Three families, in priority order:

1. **Distress** - uncredited funds, failed deposits, a frozen account,
   an unauthorised transaction. These skip the normal flow entirely and
   escalate, because the worst outcome is a worried person being handed a
   self-service article while their money is missing.
2. **Advisory** - anything asking what to buy, sell or hold, or where a price
   is headed. Refused with a disclaimer and redirected to data the user can
   read for themselves.
3. **Returns promises** - "guaranteed", "how much will I make". Answered with
   an illustration, never a forecast.

All three are plain pattern matches, not model judgements. A rule that can be
talked around by rephrasing is not a compliance control, and the model never
gets a vote on whether something counts as advice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional

Family = Literal["distress", "advisory", "projection"]

# --- 1. distress: escalate immediately --------------------------------------
_DISTRESS = re.compile(
    r"\b("
    r"money (is )?(not|hasn'?t|has not) (been )?(credit|received|reach)\w*|"
    r"not credited|uncredited|no credit|amount debited but|debited but not|"
    r"deducted but not|failed (deposit|payment|transaction|transfer)|"
    r"deposit failed|payment failed|transaction failed|"
    # Allow words between the noun and the state: "my account is STILL frozen"
    # must escalate exactly like "my account is frozen". A second attempt at
    # reporting the same emergency is not a lower-priority message.
    r"account\b[^.?!]{0,24}?\b(frozen|blocked|locked|suspended|restricted)|"
    r"(frozen|blocked|locked|suspended) account|cannot (log ?in|access my account)|"
    r"unauthori[sz]ed|unauthorised transaction|fraud|fraudulent|"
    r"someone else (placed|made|used)|i did not (place|make|authorise|authorize)|"
    r"didn'?t place this order|hacked|stolen|"
    r"missing (money|funds|amount)|where is my money"
    r")\b",
    re.I,
)

# --- 2. advisory: refuse, then redirect -------------------------------------
_ADVISORY = re.compile(
    r"\b("
    r"should i (buy|sell|invest|hold|exit|book|switch|redeem|put)|"
    r"shall i (buy|sell|invest|hold|exit)|"
    r"is .{0,40}\b(a )?(good|bad|safe|great|solid|smart|wise|bad) (buy|sell|invest|stock|bet|pick|option|choice|time)|"
    r"(good|right|best) time to (buy|sell|enter|exit|invest)|"
    r"which (stock|share|fund|scheme|sip) should i|"
    r"what should i (buy|sell|invest|do with)|"
    r"(best|top) (stock|share|fund|scheme|sip|pick)s? (to|for)|"
    # "recommend me a GOOD fund" - allow an adjective before the noun.
    r"recommend (me )?(a |an |some |any )?(\w+ ){0,2}(stock|share|fund|scheme|sip)|"
    r"do you recommend|your recommendation|any tips|stock tip|"
    r"target price|price target|will .{0,30}\b(go up|go down|rise|fall|crash|double|rally)|"
    r"is .{0,30} going to (go up|go down|rise|fall|crash)|"
    r"worth (buying|selling|investing|holding)|"
    r"multibagger|sure ?shot|guaranteed return"
    r")\b",
    re.I,
)

# --- 3. projection: illustrate, never forecast ------------------------------
_PROJECTION = re.compile(
    r"\b("
    r"guarantee\w*|assured return|fixed return|risk[- ]free|"
    r"how much will i (make|get|earn|have)|"
    r"how much (profit|money) will|what will my returns be"
    r")\b",
    re.I,
)


@dataclass(frozen=True)
class Verdict:
    family: Family
    matched: str


def check(message: str) -> Optional[Verdict]:
    """The highest-priority rule the message trips, or None."""
    text = message or ""
    for family, pattern in (("distress", _DISTRESS),
                            ("advisory", _ADVISORY),
                            ("projection", _PROJECTION)):
        found = pattern.search(text)
        if found:
            return Verdict(family=family, matched=found.group(0))  # type: ignore[arg-type]
    return None


#: Shown whenever an advisory question is declined. Says what we cannot do,
#: then what we can, so the turn ends with a route forward rather than a wall.
ADVISORY_DISCLAIMER = (
    "I can't suggest what to buy, sell or hold, or say where a price is headed "
    "— that would be investment advice, and I'm not licensed to give it. "
    "What I can do is pull up the numbers so you can judge for yourself."
)

PROJECTION_DISCLAIMER = (
    "No return can be guaranteed — market-linked investments go down as well "
    "as up. I can run an illustration at a rate you choose, but it's arithmetic, "
    "not a forecast."
)


def extract_symbol(message: str) -> Optional[str]:
    """Best guess at which instrument an advisory question was about.

    Only used to make the redirect concrete ("here's where to read about Tata
    Motors"). A miss costs nothing; the refusal stands either way.
    """
    from .data.users import USERS

    text = (message or "").lower()
    for user in USERS.values():
        for holding in user["holdings"]:
            if holding["name"].lower() in text or holding["symbol"].lower() in text:
                return holding["name"]
    known = {
        "tata motors": "Tata Motors", "tatamotors": "Tata Motors",
        "infosys": "Infosys", "infy": "Infosys",
        "hdfc bank": "HDFC Bank", "hdfcbank": "HDFC Bank",
        "reliance": "Reliance Industries", "tcs": "TCS",
        "itc": "ITC", "sbi": "State Bank of India",
        "nifty": "Nifty 50", "sensex": "Sensex",
    }
    for needle, label in known.items():
        if needle in text:
            return label
    return None
