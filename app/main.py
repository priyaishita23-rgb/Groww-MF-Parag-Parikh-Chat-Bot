"""FastAPI app: the chat endpoint, the profile switcher, and the static UI.

    uvicorn app.main:app --reload --port 8080

The chat endpoint streams newline-delimited JSON rather than returning one
blob, so the browser can show text arriving while the cards are still being
assembled. Events:

    {"type": "token", "v": "..."}     a slice of the reply text
    {"type": "card",  "card": {...}}  a structured block to render
    {"type": "chips", "chips": [...]} quick replies for the next turn
    {"type": "meta",  ...}            which tool ran, which guardrail fired
    {"type": "done"}

The agent itself is synchronous and pure - `respond()` takes a message and
returns a `Reply`. Streaming is presentation, applied here, so the agent stays
straightforward to test.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import default_chips, respond
from .data.users import DEFAULT_USER_ID, get_user, list_users
from .models import Message
from .session import STORE
from .tools import get_user_portfolio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")

app = FastAPI(title="Support Assistant", version="1.0.0")


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ProfileRequest(BaseModel):
    session_id: str
    user_id: str


def _chunk(text: str):
    """Split into small pieces so streaming looks like typing, not a dump."""
    words = text.split(" ")
    buffer = ""
    for word in words:
        buffer += (" " if buffer else "") + word
        if len(buffer) >= 14:
            yield buffer
            buffer = ""
    if buffer:
        yield buffer


async def _stream(message: str, session_id: Optional[str]) -> AsyncIterator[bytes]:
    session = STORE.get_or_create(session_id)
    session.append(Message(role="user", text=message))

    reply = respond(message, session_id=session.session_id, user_id=session.user_id)

    def event(payload: Dict[str, Any]) -> bytes:
        return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")

    yield event({"type": "session", "session_id": session.session_id})

    for piece in _chunk(reply.text):
        yield event({"type": "token", "v": piece})
        await asyncio.sleep(0.022)

    for card in reply.cards:
        yield event({"type": "card", "card": card.to_dict()})
        await asyncio.sleep(0.06)

    if reply.chips:
        yield event({"type": "chips", "chips": [c.to_dict() for c in reply.chips]})

    yield event({"type": "meta", "tool": reply.tool, "guardrail": reply.guardrail})
    yield event({"type": "done"})

    session.append(Message(role="assistant", text=reply.text, cards=reply.cards))


@app.post("/api/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _stream(request.message, request.session_id),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.post("/api/chat/sync")
async def chat_sync(request: ChatRequest) -> Dict[str, Any]:
    """Non-streaming equivalent. Used by the tests and easier to curl."""
    session = STORE.get_or_create(request.session_id)
    session.append(Message(role="user", text=request.message))
    reply = respond(request.message, session_id=session.session_id,
                    user_id=session.user_id)
    session.append(Message(role="assistant", text=reply.text, cards=reply.cards))
    return {"session_id": session.session_id, **reply.to_dict()}


@app.get("/api/portfolio")
async def portfolio(user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Portfolio data for the dashboard tiles.

    The tiles are a data read, not a conversation, and they used to be fetched
    by asking the chat endpoint "show my portfolio" under a synthetic session
    id. That was wrong twice over: it invented a session per profile that the
    store then had to keep, and a fresh session always starts on the default
    user - so switching profile never changed the tiles.
    """
    result = get_user_portfolio(user_id)
    return {"user_id": user_id,
            "card": result.cards[0].to_dict() if result.cards else None}


@app.get("/api/session")
async def session_state(session_id: Optional[str] = None) -> Dict[str, Any]:
    session = STORE.get_or_create(session_id)
    user = get_user(session.user_id)
    return {
        "session_id": session.session_id,
        "user": {"user_id": user["user_id"], "name": user["name"],
                 "persona": user["persona"]},
        "profiles": list_users(),
        "messages": [m.to_dict() for m in session.messages],
        "chips": [c.to_dict() for c in default_chips()],
    }


@app.post("/api/session/profile")
async def switch_profile(request: ProfileRequest) -> Dict[str, Any]:
    session = STORE.set_user(request.session_id, request.user_id)
    user = get_user(session.user_id)
    return {
        "session_id": session.session_id,
        "user": {"user_id": user["user_id"], "name": user["name"],
                 "persona": user["persona"]},
        "messages": [],
        "chips": [c.to_dict() for c in default_chips()],
    }


@app.post("/api/session/reset")
async def reset(request: ProfileRequest) -> Dict[str, Any]:
    session = STORE.reset(request.session_id)
    return {"session_id": session.session_id, "messages": []}


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    return {"ok": True, "sessions": STORE.count()}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(os.path.join(WEB, "index.html"))


app.mount("/static", StaticFiles(directory=WEB), name="static")
