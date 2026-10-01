"""In-memory chat sessions.

Process-local and deliberately so: this is a prototype, and a real deployment
would put this behind Redis or a database. What matters is that the interface
is small enough to swap - get, append, reset - so replacing the store does not
touch the agent.

Sessions expire so a long-running demo does not grow without bound.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .data.users import DEFAULT_USER_ID
from .models import Message

MAX_TURNS = 40
TTL_SECONDS = 60 * 60 * 4


@dataclass
class Session:
    session_id: str
    user_id: str = DEFAULT_USER_ID
    messages: List[Message] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    touched: float = field(default_factory=time.time)

    def append(self, message: Message) -> None:
        self.messages.append(message)
        # Keep the tail; the agent only needs recent context and unbounded
        # growth is how a demo left open overnight eats memory.
        if len(self.messages) > MAX_TURNS:
            self.messages = self.messages[-MAX_TURNS:]
        self.touched = time.time()


class SessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def _sweep(self) -> None:
        cutoff = time.time() - TTL_SECONDS
        stale = [sid for sid, s in self._sessions.items() if s.touched < cutoff]
        for sid in stale:
            self._sessions.pop(sid, None)

    def get_or_create(self, session_id: Optional[str]) -> Session:
        with self._lock:
            self._sweep()
            if session_id and session_id in self._sessions:
                return self._sessions[session_id]
            new_id = session_id or secrets.token_urlsafe(12)
            session = Session(session_id=new_id)
            self._sessions[new_id] = session
            return session

    def reset(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            user_id = session.user_id if session else DEFAULT_USER_ID
            fresh = Session(session_id=session_id, user_id=user_id)
            self._sessions[session_id] = fresh
            return fresh

    def set_user(self, session_id: str, user_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = Session(session_id=session_id)
                self._sessions[session_id] = session
            # Switching profile starts a new conversation: the previous one is
            # about someone else's money and must not carry over.
            session.user_id = user_id
            session.messages = []
            session.touched = time.time()
            return session

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)


STORE = SessionStore()
