"""calculateReturns(sipAmount, tenureYears, expectedRate) - an illustration.

Deliberately framed as arithmetic rather than a projection. The card carries a
disclaimer line, and the rate is always shown as the user's assumption, not
ours - "at 12%" is a number they chose, and the UI says so.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from ..models import Card, Chip, ToolResult

DEFAULT_AMOUNT = 5000.0
DEFAULT_YEARS = 10.0
DEFAULT_RATE = 12.0


def _money(value: float) -> str:
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
    return "₹%s" % whole


def calculate_returns(sip_amount: float, tenure_years: float,
                      expected_rate: float) -> ToolResult:
    sip_amount = max(float(sip_amount), 100.0)
    tenure_years = min(max(float(tenure_years), 0.5), 40.0)
    expected_rate = min(max(float(expected_rate), 0.0), 30.0)

    months = int(round(tenure_years * 12))
    monthly_rate = expected_rate / 100.0 / 12.0

    # Future value of an annuity-due: each instalment compounds from the month
    # it is paid, and SIP instalments are paid at the start of the period.
    if monthly_rate == 0:
        future_value = sip_amount * months
    else:
        future_value = (sip_amount
                        * ((pow(1 + monthly_rate, months) - 1) / monthly_rate)
                        * (1 + monthly_rate))

    invested = sip_amount * months
    gain = future_value - invested

    # A yearly series so the card can draw the split without recomputing.
    series = []
    for year in range(1, int(round(tenure_years)) + 1):
        m = year * 12
        if monthly_rate == 0:
            v = sip_amount * m
        else:
            v = (sip_amount * ((pow(1 + monthly_rate, m) - 1) / monthly_rate)
                 * (1 + monthly_rate))
        series.append({"year": year,
                       "invested": round(sip_amount * m, 2),
                       "value": round(v, 2)})

    data = {
        "sip_amount": sip_amount,
        "tenure_years": tenure_years,
        "expected_rate": expected_rate,
        "months": months,
        "invested": round(invested, 2),
        "future_value": round(future_value, 2),
        "gain": round(gain, 2),
        "multiple": round(future_value / invested, 2) if invested else 0.0,
        "series": series,
        "disclaimer": ("An illustration at a rate you chose, not a forecast. "
                       "Actual returns vary and can be negative."),
    }

    text = ("Putting in %s a month for %g years at %g%% would total %s invested, "
            "illustrating to about %s."
            % (_money(sip_amount), tenure_years, expected_rate,
               _money(invested), _money(future_value)))

    return ToolResult(
        text=text,
        cards=[Card(kind="sip_projection", data=data)],
        chips=[
            Chip("Try 15 years", "SIP of %d for 15 years at %g%%"
                 % (int(sip_amount), expected_rate)),
            Chip("Try a lower rate", "SIP of %d for %g years at 8%%"
                 % (int(sip_amount), tenure_years)),
            Chip("Check my SIP", "What is the status of my SIP?"),
        ],
        raw=data,
    )


_AMOUNT = re.compile(r"(?:₹|rs\.?\s*|inr\s*)?(\d[\d,]{2,})\s*(k)?\b", re.I)
_YEARS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?|y)\b", re.I)
# The word boundary has to sit INSIDE the word alternatives. Written as
# `(?:%|percent)\b` a trailing "12%" never matches: `%` is not a word
# character, so there is no boundary between it and the end of the string, and
# the rate silently falls back to the default. The first version of this
# passed its test only because the default happened to be the expected value.
_RATE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|(?:percent|per cent|pc)\b)", re.I)


def parse_request(message: str) -> Tuple[float, float, float]:
    """Pull amount, tenure and rate out of free text, with sane defaults."""
    text = message or ""

    years: Optional[float] = None
    found = _YEARS.search(text)
    if found:
        years = float(found.group(1))

    rate: Optional[float] = None
    found = _RATE.search(text)
    if found:
        rate = float(found.group(1))

    amount: Optional[float] = None
    for m in _AMOUNT.finditer(text):
        value = float(m.group(1).replace(",", ""))
        if m.group(2):          # "5k"
            value *= 1000
        # Skip numbers already claimed as the tenure or the rate.
        if years is not None and value == years:
            continue
        if rate is not None and value == rate:
            continue
        if value >= 100:
            amount = value
            break

    return (amount if amount is not None else DEFAULT_AMOUNT,
            years if years is not None else DEFAULT_YEARS,
            rate if rate is not None else DEFAULT_RATE)
