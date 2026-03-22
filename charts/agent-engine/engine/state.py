from __future__ import annotations

import json
from datetime import datetime, timezone

import aiosqlite


class State:
    """Workflow execution state. Simple dict-based, not LangGraph's reducer system."""

    def __init__(self, thread_id: str, config_snapshot: dict, params: dict):
        self.thread_id = thread_id
        self.messages: list[dict] = []
        self.params: dict = params
        self.counters: dict[str, int] = {}
        self.flow_position: list = []
        self.config_snapshot: dict = config_snapshot

    def add_message(self, message: dict):
        """Append a message (user, assistant, tool) to history."""
        self.messages.append(message)

    def add_messages(self, messages: list[dict]):
        """Append multiple messages."""
        self.messages.extend(messages)

    def get_counter(self, name: str, default: int = 0) -> int:
        return self.counters.get(name, default)

    def increment_counter(self, name: str):
        self.counters[name] = self.counters.get(name, 0) + 1

    def reset_counter(self, name: str):
        self.counters.pop(name, None)

    def to_dict(self) -> dict:
        """Serialize full state for checkpointing."""
        return {
            "thread_id": self.thread_id,
            "messages": self.messages,
            "params": self.params,
            "counters": self.counters,
            "flow_position": self.flow_position,
            "config_snapshot": self.config_snapshot,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "State":
        """Restore from checkpoint."""
        state = cls(data["thread_id"], data["config_snapshot"], data["params"])
        state.messages = data["messages"]
        state.counters = data["counters"]
        state.flow_position = data["flow_position"]
        return state


class CheckpointStore:
    """Async SQLite-backed checkpoint store for workflow state."""

    _CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id  TEXT PRIMARY KEY,
            state      TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """

    def __init__(self, db_path: str):
        self._db_path = db_path

    async def init(self):
        """Create the checkpoints table if it does not already exist."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(self._CREATE_TABLE)
            await db.commit()

    async def save(self, state: State):
        """Persist state as JSON, replacing any existing checkpoint for the thread."""
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(state.to_dict())
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO checkpoints (thread_id, state, updated_at) VALUES (?, ?, ?)",
                (state.thread_id, payload, now),
            )
            await db.commit()

    async def load(self, thread_id: str) -> State | None:
        """Return the saved State for thread_id, or None if not found."""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT state FROM checkpoints WHERE thread_id = ?",
                (thread_id,),
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            return None
        return State.from_dict(json.loads(row[0]))

    async def delete(self, thread_id: str):
        """Remove a checkpoint."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "DELETE FROM checkpoints WHERE thread_id = ?",
                (thread_id,),
            )
            await db.commit()
