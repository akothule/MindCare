from collections import deque
from threading import Lock
from typing import Deque, Optional
from uuid import uuid4

from mindcare.config import get_settings
from mindcare.schemas import ChatRequest


class SessionStore:
    """In-memory session history (MVP). Lost on restart."""

    def __init__(self) -> None:
        self._sessions: dict[str, Deque[dict[str, str]]] = {}
        self._high_risk_counts: dict[str, int] = {}
        self._lock = Lock()

    def _maxlen(self) -> int:
        return get_settings().max_session_messages

    def get_or_create_session_id(self, request: ChatRequest) -> str:
        if request.session_id and request.session_id.strip():
            sid = request.session_id.strip()
            with self._lock:
                if sid not in self._sessions:
                    self._sessions[sid] = deque(maxlen=self._maxlen())
                self._high_risk_counts.setdefault(sid, 0)
            return sid
        new_id = str(uuid4())
        with self._lock:
            self._sessions[new_id] = deque(maxlen=self._maxlen())
            self._high_risk_counts[new_id] = 0
        return new_id

    def append_user_message(self, session_id: str, text: str) -> None:
        with self._lock:
            self._sessions.setdefault(session_id, deque(maxlen=self._maxlen())).append(
                {"role": "user", "content": text}
            )

    def append_assistant_message(self, session_id: str, text: str) -> None:
        with self._lock:
            self._sessions.setdefault(session_id, deque(maxlen=self._maxlen())).append(
                {"role": "assistant", "content": text}
            )

    def history_for_prompt(self, session_id: str) -> list[dict[str, str]]:
        with self._lock:
            q = self._sessions.get(session_id)
            if not q:
                return []
            return list(q)

    def increment_high_risk(self, session_id: str) -> int:
        with self._lock:
            self._high_risk_counts[session_id] = self._high_risk_counts.get(session_id, 0) + 1
            return self._high_risk_counts[session_id]

    def high_risk_count(self, session_id: str) -> int:
        with self._lock:
            return self._high_risk_counts.get(session_id, 0)


_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
