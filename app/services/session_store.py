"""
UUID-based in-memory session store for multi-user isolation.

Each browser session gets a unique UUID stored in an HTTP-only cookie.
Session data is held in memory — suitable for single-process deployments.
If the process restarts, sessions are cleared (users must re-upload).
"""

import uuid
import threading
from typing import Any


class SessionStore:
    """Thread-safe, UUID-keyed in-memory session store."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self) -> str:
        """Create a new empty session and return its UUID."""
        session_id = str(uuid.uuid4())
        with self._lock:
            self._store[session_id] = {}
        return session_id

    def get(self, session_id: str) -> dict[str, Any]:
        """Return the session data dict (creates empty session if missing)."""
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = {}
            return self._store[session_id]

    def set(self, session_id: str, key: str, value: Any) -> None:
        """Set a single key inside a session."""
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = {}
            self._store[session_id][key] = value

    def update(self, session_id: str, data: dict[str, Any]) -> None:
        """Merge a dict of key-value pairs into the session."""
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = {}
            self._store[session_id].update(data)

    def delete(self, session_id: str) -> None:
        """Remove an entire session."""
        with self._lock:
            self._store.pop(session_id, None)

    def exists(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._store


# Module-level singleton used by route handlers
store = SessionStore()

COOKIE_NAME = "loom_session"
