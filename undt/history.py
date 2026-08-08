"""Per-visitor continuity.

The API is stateless and so is the model, but an application that forgets
what it served ten seconds ago isn't an application. Each visitor gets a
short rolling log of exchanges plus a longer-lived set of notes the model
writes for itself.
"""

from __future__ import annotations

import threading
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Exchange:
    method: str
    path: str
    response: str
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out = {"request": f"{self.method} {self.path}", "response": self.response}
        if self.note:
            out["note"] = self.note
        return out


@dataclass
class Session:
    exchanges: deque[Exchange]
    memory: list[str] = field(default_factory=list)


class SessionStore:
    """An in-memory, bounded, thread-safe store of visitor sessions.

    Deliberately not durable. Restart the server and the world forgets.
    """

    def __init__(
        self,
        *,
        max_sessions: int = 256,
        max_exchanges: int = 12,
        max_memory: int = 60,
    ) -> None:
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._lock = threading.Lock()
        self._max_sessions = max_sessions
        self._max_exchanges = max_exchanges
        self._max_memory = max_memory

    def snapshot(self, session_id: str) -> tuple[list[dict[str, Any]], list[str]]:
        """The history and memory to show the model for this request."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return [], []
            self._sessions.move_to_end(session_id)
            return [e.as_dict() for e in session.exchanges], list(session.memory)

    def record(
        self,
        session_id: str,
        exchange: Exchange,
        new_memory: list[str] | None = None,
    ) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = Session(exchanges=deque(maxlen=self._max_exchanges))
                self._sessions[session_id] = session
                while len(self._sessions) > self._max_sessions:
                    self._sessions.popitem(last=False)

            self._sessions.move_to_end(session_id)
            session.exchanges.append(exchange)

            for note in new_memory or []:
                if note not in session.memory:
                    session.memory.append(note)
            del session.memory[: max(0, len(session.memory) - self._max_memory)]

    def forget(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
