"""Behaviour tests. python -m unittest discover -s tests -v

The compliance cases are the ones that matter. A support assistant that
answers "should I buy Tata Motors?" with anything other than a refusal is a
regulatory problem, not a UX one, so those are asserted hard.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import guardrails  # noqa: E402
from app.agent import respond  # noqa: E402
from app.tools.returns import calculate_returns, parse_request  # noqa: E402

NEW_INVESTOR = "U1001"
TRADER = "U2002"


def ask(text, user=NEW_INVESTOR, session="t-session"):
    return respond(text, session_id=session, user_id=user)


class Advisory(unittest.TestCase):
    """SEBI guardrail: never a stock pick, a recommendation or a target."""

    REFUSE = [
        "Should I buy Tata Motors?",
        "should i sell my infosys",
        "Is HDFC Bank a good buy right now?",
        "which stock should i buy",
        "what is the target price for ITC",
        "will Tata Motors go up next week",
        "recommend me a good fund",
        "best stocks to buy today",
        "is it a good time to invest",
        "any tips for multibagger stocks",
        "do you recommend the midcap fund",
        "worth buying more infosys?",
    ]

    def test_every_advisory_question_is_refused(self):
        for question in self.REFUSE:
            with self.subTest(q=question):
                reply = ask(question)
                self.assertEqual(reply.guardrail, "advisory",
                                 msg="%r was not treated as advice" % question)
                self.assertIsNone(reply.tool,
                                  msg="%r reached a tool" % question)

    def test_refusal_carries_a_disclaimer_card(self):
        reply = ask("Should I buy Tata Motors?")
        kinds = [c.kind for c in reply.cards]
        self.assertIn("disclaimer", kinds)

    def test_refusal_redirects_to_data_not_a_dead_end(self):
        reply = ask("Should I buy Tata Motors?")
        self.assertTrue(reply.chips, "a refusal must still offer a way forward")
        card = [c for c in reply.cards if c.kind == "disclaimer"][0]
        self.assertEqual(card.data["subject"], "Tata Motors")
        self.assertTrue(card.data["alternatives"])

    def test_factual_questions_are_not_caught_by_the_advice_filter(self):
        """Over-blocking is a defect too - these must still be answered."""
        for question in ["show my portfolio",
                         "what is the status of my SIP?",
                         "track order ORD-77190",
                         "explain my P&L and STCG"]:
            with self.subTest(q=question):
                reply = ask(question, user=TRADER)
                self.assertNotEqual(reply.guardrail, "advisory", msg=question)


class Escalation(unittest.TestCase):
    """Distress hands over immediately rather than troubleshooting."""

    IMMEDIATE = [
        "my deposit failed but money was debited",
        "money is not credited to my wallet",
        "my account is frozen",
        "there is an unauthorised transaction on my account",
        "I did not place this order",
        "amount debited but not credited",
        "where is my money",
        "I think my account was hacked",
    ]

    def test_distress_escalates_without_troubleshooting_first(self):
        for question in self.IMMEDIATE:
            with self.subTest(q=question):
                reply = ask(question, user=TRADER)
                self.assertEqual(reply.guardrail, "distress", msg=question)
                self.assertEqual(reply.tool, "escalateToHumanAgent", msg=question)
                self.assertTrue([c for c in reply.cards if c.kind == "ticket"],
                                msg="%r produced no ticket" % question)

    def test_money_missing_is_top_priority(self):
        reply = ask("my deposit failed but the money was debited", user=TRADER)
        ticket = [c for c in reply.cards if c.kind == "ticket"][0].data
        self.assertIn(ticket["priority"], ("P0", "P1"))
        self.assertGreaterEqual(ticket["priority_score"], 85)

    def test_unauthorised_activity_outranks_an_ordinary_query(self):
        fraud = ask("there is an unauthorised transaction", user=TRADER,
                    session="a")
        routine = ask("I want to raise a ticket about my SIP order",
                      user=TRADER, session="b")
        fraud_score = [c for c in fraud.cards if c.kind == "ticket"][0].data["priority_score"]
        routine_score = [c for c in routine.cards if c.kind == "ticket"][0].data["priority_score"]
        self.assertGreater(fraud_score, routine_score)

    def test_a_rate_at_the_end_of_the_sentence_is_read(self):
        """Regression: a trailing "9%" used to fall back to the default."""
        self.assertEqual(parse_request("for 20 years at 9%")[2], 9.0)
        self.assertEqual(parse_request("at 7.5% for 10 years")[2], 7.5)

    def test_ticket_id_is_stable_for_the_same_issue_and_session(self):
        """Rephrasing must not open a second ticket for one problem."""
        first = ask("my account is frozen", session="same")
        second = ask("my account is still frozen, please help", session="same")
        a = [c for c in first.cards if c.kind == "ticket"][0].data["ticket_id"]
        b = [c for c in second.cards if c.kind == "ticket"][0].data["ticket_id"]
        self.assertEqual(a, b)

    def test_explicit_request_for_a_human_opens_a_ticket(self):
        reply = ask("I want to speak to a human agent")
        self.assertEqual(reply.tool, "escalateToHumanAgent")


class Tools(unittest.TestCase):
    def test_portfolio_for_the_new_investor(self):
        reply = ask("show my portfolio", user=NEW_INVESTOR)
        self.assertEqual(reply.tool, "getUserPortfolio")
        data = [c for c in reply.cards if c.kind == "portfolio"][0].data
        self.assertEqual(data["holdings"], [])
        self.assertEqual(len(data["sips"]), 1)

    def test_portfolio_for_the_trader(self):
        reply = ask("show my portfolio", user=TRADER)
        data = [c for c in reply.cards if c.kind == "portfolio"][0].data
        self.assertEqual(len(data["holdings"]), 4)
        self.assertEqual(len(data["sips"]), 2)
        self.assertGreater(data["totals"]["value"], data["totals"]["invested"])

    def test_order_status_returns_a_stepper(self):
        reply = ask("track order ORD-88213", user=NEW_INVESTOR)
        self.assertEqual(reply.tool, "getTransactionStatus")
        data = [c for c in reply.cards if c.kind == "order_status"][0].data
        self.assertEqual(data["status_code"], "units_pending")
        self.assertTrue(any(s["state"] == "active" for s in data["steps"]))

    def test_unknown_order_fails_helpfully(self):
        reply = ask("track order ORD-99999")
        self.assertFalse([c for c in reply.cards if c.kind == "order_status"])
        self.assertIn("ORD-", reply.text)

    def test_withdrawal_tracking_finds_the_order_without_an_id(self):
        reply = ask("track my withdrawal", user=TRADER)
        self.assertEqual(reply.tool, "getTransactionStatus")
        data = [c for c in reply.cards if c.kind == "order_status"][0].data
        self.assertEqual(data["order_id"], "ORD-77190")

    def test_sip_calculator_maths(self):
        result = calculate_returns(5000, 10, 12)
        data = result.cards[0].data
        self.assertEqual(data["invested"], 600000)
        # Annuity-due at 12% for 120 months lands a little over 11.6 lakh.
        self.assertGreater(data["future_value"], 1_150_000)
        self.assertLess(data["future_value"], 1_180_000)

    def test_zero_rate_is_just_the_sum_of_instalments(self):
        data = calculate_returns(1000, 5, 0).cards[0].data
        self.assertAlmostEqual(data["future_value"], 60000, places=2)
        self.assertAlmostEqual(data["gain"], 0, places=2)

    def test_calculator_parses_free_text(self):
        self.assertEqual(parse_request("SIP of 5000 for 15 years at 12%"),
                         (5000.0, 15.0, 12.0))
        self.assertEqual(parse_request("invest 10,000 monthly for 20 years at 9%"),
                         (10000.0, 20.0, 9.0))

    def test_calculator_is_reached_from_natural_phrasings(self):
        """Regression: "SIP of 5000" used to miss the router entirely."""
        for question in ["SIP of 5000 for 15 years at 12%",
                         "sip of 2500 for 5 years",
                         "calculate a sip for 10 years",
                         "what would 3000 a month grow to in 20 years"]:
            with self.subTest(q=question):
                reply = ask(question)
                self.assertEqual(reply.tool, "calculateReturns", msg=question)
                self.assertIn("sip_projection", [c.kind for c in reply.cards])

    def test_calculator_reads_the_numbers_it_was_given(self):
        reply = ask("SIP of 5000 for 15 years at 12%")
        data = [c for c in reply.cards if c.kind == "sip_projection"][0].data
        self.assertEqual(data["sip_amount"], 5000)
        self.assertEqual(data["tenure_years"], 15)
        self.assertEqual(data["expected_rate"], 12)

    def test_calculator_defaults_when_nothing_is_given(self):
        amount, years, rate = parse_request("can you calculate a sip for me")
        self.assertEqual((amount, years, rate), (5000.0, 10.0, 12.0))


class Projection(unittest.TestCase):
    def test_guaranteed_return_question_gets_a_disclaimer_first(self):
        reply = ask("how much will I make if I invest 5000 for 10 years")
        self.assertEqual(reply.guardrail, "projection")
        self.assertEqual(reply.cards[0].kind, "disclaimer")
        self.assertIn("sip_projection", [c.kind for c in reply.cards])


class Conversation(unittest.TestCase):
    def test_greeting_offers_quick_actions(self):
        reply = ask("hi")
        self.assertTrue(reply.chips)

    def test_unknown_question_does_not_invent_an_answer(self):
        reply = ask("what is the airspeed velocity of an unladen swallow")
        self.assertIsNone(reply.tool)
        self.assertTrue(reply.chips)

    def test_every_reply_has_text(self):
        for question in ["hi", "show my portfolio", "should i buy itc",
                         "my account is frozen", "track ORD-77190", ""]:
            with self.subTest(q=question):
                self.assertTrue(ask(question, user=TRADER).text.strip())

    def test_new_investor_has_no_withdrawal_to_track(self):
        reply = ask("track my withdrawal", user=NEW_INVESTOR)
        self.assertFalse([c for c in reply.cards if c.kind == "order_status"])


class GuardrailUnits(unittest.TestCase):
    def test_priority_order_distress_beats_advisory(self):
        """A frozen account mentioned alongside advice is still an emergency."""
        verdict = guardrails.check("my account is frozen, should i sell everything")
        self.assertEqual(verdict.family, "distress")

    def test_plain_questions_trip_nothing(self):
        for question in ["show my portfolio", "track ORD-88213",
                         "what is my wallet balance", "hi"]:
            with self.subTest(q=question):
                self.assertIsNone(guardrails.check(question))


if __name__ == "__main__":
    unittest.main()
