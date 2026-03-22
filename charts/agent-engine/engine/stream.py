from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator


class StreamWriter:
    """Manages SSE event streaming to clients.

    Supports two modes:
    - Sequential (single agent): stream tokens in real-time.
    - Parallel (multiple agents): buffer per-agent, emit blocks on completion.
    """

    def __init__(self):
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()
        self._closed = False

    # ------------------------------------------------------------------
    # Low-level primitives
    # ------------------------------------------------------------------

    def emit(self, event: dict):
        """Enqueue a raw SSE event dict. Safe to call from sync or async code."""
        if not self._closed:
            self._queue.put_nowait(event)

    def close(self):
        """Signal end of stream. Subsequent emit() calls are silently dropped."""
        self._closed = True
        self._queue.put_nowait(None)  # sentinel

    async def events(self) -> AsyncGenerator[str, None]:
        """Async generator yielding SSE-formatted strings."""
        while True:
            event = await self._queue.get()
            if event is None:
                yield "data: [DONE]\n\n"
                break
            yield f"data: {json.dumps(event)}\n\n"

    # ------------------------------------------------------------------
    # Typed helpers — emit well-known event shapes
    # ------------------------------------------------------------------

    def step_start(self, agent: str):
        """Agent begins executing."""
        self.emit({"type": "step_start", "agent": agent})

    def token(self, agent: str, text: str):
        """Single streaming token from an LLM response."""
        self.emit({"type": "token", "agent": agent, "token": text})

    def researching(self, agent: str, queries: list[str]):
        """Agent is issuing tool / search calls."""
        self.emit({"type": "researching", "agent": agent, "queries": queries})

    def content(self, agent: str, text: str):
        """Complete content block, used in parallel mode after agent finishes."""
        self.emit({"type": "content", "agent": agent, "content": text})

    def route(self, matched: str, next_step: str):
        """Router matched a pattern and is branching to next_step."""
        self.emit({"type": "route", "matched": matched, "next": next_step})

    def loop_iteration(self, iteration: int, max_iterations: int):
        """Progress indicator for iterative loops."""
        self.emit({"type": "loop_iteration", "iteration": iteration, "max": max_iterations})

    def step_end(self, agent: str):
        """Agent finished executing."""
        self.emit({"type": "step_end", "agent": agent})

    def error(self, agent: str, message: str):
        """Non-fatal error from a specific agent."""
        self.emit({"type": "error", "agent": agent, "message": message})

    def complete(self, result: str):
        """Workflow finished; close the stream after emitting the final result."""
        self.emit({"type": "complete", "result": result})
        self.close()
