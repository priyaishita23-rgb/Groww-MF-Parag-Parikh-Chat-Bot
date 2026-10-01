# Support Assistant

An interactive support assistant for an investing app — stocks, mutual funds, SIPs
and account services. It answers from mock domain tools, renders structured cards
rather than text dumps, and refuses to give investment advice.

Python throughout. FastAPI for the streaming API, hand-written CSS and vanilla JS
for the UI, so there is no Node toolchain and no build step.

---

## Run it

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8080
```

Open <http://127.0.0.1:8080>. The chat launcher is at the bottom right.

```bash
python -m unittest discover -s tests -v
```

Nothing calls an external service and there is no API key: every tool is a
deterministic mock, so the same question gives the same answer every time.

---

## What to try

Pick a demo profile from the header — the assistant's answers change with it.

| Ask this | What should happen |
|---|---|
| `What is the status of my SIP?` | Order stepper: debited → sent to AMC → **units pending** → portfolio |
| `Track order ORD-77190` | Withdrawal stepper with the bank UTR *(Vikram's profile)* |
| `Show my portfolio` | Holdings, SIPs, wallet, P&L per line |
| `SIP of 5000 for 15 years at 12%` | Calculator card with a year-by-year invested/growth split |
| **`Should I buy Tata Motors?`** | **Refused.** Compliance notice + redirect to fundamentals |
| **`My deposit failed but money was debited`** | **Escalates immediately.** P1 ticket, priority 90/100 |
| `Explain my P&L and STCG` | Plain-language tax explanation + your portfolio |
| `Why does unit allotment take T+2 days?` | Explains the AMC allotment cycle |
| `I want to speak to a human agent` | Opens a ticket |
| `What is the capital of France?` | Says it doesn't know, offers what it can do |

### The two profiles

| | **Ananya Rao** `U1001` | **Vikram Shetty** `U2002` |
|---|---|---|
| Persona | New investor | Active equity trader |
| Holdings | none | 4 stocks |
| SIPs | 1 active | 1 active, 1 paused |
| Orders | SIP instalment, units pending | Withdrawal in progress, **failed deposit** |

Vikram's failed deposit exists to exercise escalation. Ask *"my deposit failed but
money was debited"* on his profile.

---

## Header navigation

All five header sections — **Investments, Dashboard, Stocks, Mutual funds, Orders** —
open a flyout of grouped options. Click elsewhere, press `Escape`, or click the
section again to close; only one opens at a time.

Items marked **ASK** are wired to the assistant: clicking one opens the chat and runs
it, so the navigation demonstrates the product rather than going nowhere.

| Item | Runs |
|---|---|
| Stocks · My holdings · Overview | Portfolio card |
| My SIPs · SIP instalments | Order stepper |
| SIP calculator | Calculator card |
| Withdrawals | Withdrawal stepper |
| **Failed payment** | Escalation + P1 ticket |
| P&L and tax | Tax explanation |

Items with no mock data behind them — F&O, Gold, US stocks, Watchlist — are dimmed
and inert. A nav full of links that quietly do nothing is worse than one that shows
which parts are real.

Menus live in `MENUS` at the top of `web/app.js`; each entry is `{ title, items }`
and an item becomes interactive purely by having a `send` string.

On narrow screens the nav drops to its own row and scrolls sideways rather than being
hidden, so every section stays reachable.

---

## How a turn works

```
message
   │
   ├─ 1. guardrails ──── distress?   → escalate, skip everything else
   │                     advisory?   → refuse + disclaimer card
   │                     projection? → disclaimer, then an illustration
   │
   ├─ 2. hand-off ────── explicit request for a human → ticket
   │
   ├─ 3. tool ────────── order id · calculator · portfolio · orders · tracking
   │
   └─ 4. reply ───────── text + cards + quick-reply chips
```

**Guardrails run first and can end the turn.** Nothing downstream can overturn them.

**Tool selection is deterministic** — patterns, not a model's judgement. On a support
surface the wrong branch means a frozen-account report gets answered with an FAQ
link, so predictability beats cleverness, and every route has a test.
`SCHEMAS` in `app/tools/__init__.py` declares the same tools in function-calling
shape, so a model-driven planner can replace the router later without touching the
tools or the guardrails.

### Compliance

| Rule | Behaviour |
|---|---|
| **No advice** | No stock picks, no buy/sell/hold, no price targets. Refused with a disclaimer and redirected to data the user can read themselves |
| **No guaranteed returns** | The calculator is framed as arithmetic at a rate *the user chose*, never a forecast |
| **Immediate hand-off** | Uncredited funds, failed deposits, frozen accounts and unauthorised transactions escalate straight away, before any troubleshooting |

These are plain pattern matches. A rule that can be talked around by rephrasing is
not a compliance control, so the model never gets a vote on what counts as advice.

Over-blocking is treated as a defect too: `test_factual_questions_are_not_caught_by_the_advice_filter`
holds the line from the other side, so "show my portfolio" is never mistaken for a
request for a recommendation.

**Ticket IDs are stable per session and issue.** Rephrasing a problem reuses the same
ticket instead of opening a second one — otherwise one problem becomes five open
tickets and nobody owns any of them.

---

## Branding

Two assets in `web/brand/`:

| File | Used by | Notes |
|---|---|---|
| `logo.webp` | header mark, chat avatar, favicon | 240×240; drawn as a circle at 26px and 34px |
| `wordmark.png` | header lockup | 109×44; drawn at 21px tall |

The header reads **mark · wordmark · divider · "Investments"**, and the chat titles
itself *Groww Support Assistant*, so it is clear whose assistant this is from either
surface.

Replacing either file is enough on its own — no code change — as long as the names
stay the same.

**`wordmark.png` has no alpha channel**: it carries a white background, which is
invisible on the white header bar and would show as a white box anywhere else. Swap
in an SVG or a transparent PNG before putting it on a coloured surface.

The mark is clipped to a circle, so a square logo needs `border-radius` dropped from
`.brand-mark` and `.avatar` in `web/styles.css`.

WebP favicons work in current Chrome, Edge, Firefox and Safari. Add a `.png` and a
second `<link rel="icon">` for older browsers.

Accent colour is one CSS variable, `--accent` in `web/styles.css`.

---

## Layout

```
app/
  main.py          FastAPI: streaming chat, profile switch, static UI
  agent.py         guardrails → tool → reply
  guardrails.py    distress / advisory / projection rules
  session.py       in-memory sessions with a TTL
  models.py        Card, Chip, Reply, ToolResult
  data/users.py    the two mock profiles and their orders
  tools/
    portfolio.py      getUserPortfolio
    transactions.py   getTransactionStatus
    returns.py        calculateReturns
    escalation.py     escalateToHumanAgent
    __init__.py       the function-calling SCHEMAS
web/
  index.html  styles.css  app.js      no build step
tests/test_agent.py                   28 tests
```

### API

| Route | Purpose |
|---|---|
| `POST /api/chat` | Streams newline-delimited JSON: `token`, `card`, `chips`, `meta`, `done` |
| `POST /api/chat/sync` | Same turn, one JSON response. Easier to curl, used by tests |
| `GET /api/session` | Session state, profiles, starting chips |
| `POST /api/session/profile` | Switch demo profile (clears the conversation) |
| `GET /healthz` | Liveness |

```bash
curl -s -X POST localhost:8080/api/chat/sync \
  -H 'content-type: application/json' \
  -d '{"message":"Should I buy Tata Motors?"}'
```

The agent is synchronous and pure: `respond(message, session_id, user_id) -> Reply`.
Streaming is presentation, applied in `main.py`, which keeps the agent easy to test.

---

## Known limits

- **Sessions are in-process.** Restarting the server loses them. The store's
  interface is deliberately small — get, append, reset — so Redis or a database can
  replace it without touching the agent.
- **Every tool is a fixed mock.** No prices move, no clock advances, and figures are
  hard-coded so a demo is repeatable.
- **The router is pattern-based**, so an unusual phrasing falls through to the "I'm
  not sure I followed that" reply rather than being answered loosely. That is the
  intended failure mode here, but it does cost recall.
- **Switching profile clears the conversation.** The previous one is about someone
  else's money and must not carry over.
- **Not a real account.** Mock data, a prototype, and not investment advice.
