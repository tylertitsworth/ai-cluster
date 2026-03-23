"""Tests for engine.stream.StreamWriter."""

import asyncio
import json

import pytest

from engine.stream import StreamWriter


async def _collect_sse(writer: StreamWriter) -> list[str]:
    chunks: list[str] = []
    async for line in writer.events():
        chunks.append(line)
    return chunks


def _drain_raw_events(writer: StreamWriter) -> list[dict]:
    """Pop all pending dict events from the writer queue (no sentinel expected)."""
    out: list[dict] = []
    while True:
        try:
            item = writer._queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        assert item is not None, "unexpected stream sentinel while draining typed events"
        out.append(item)
    return out


@pytest.mark.asyncio
async def test_emit_and_consume():
    writer = StreamWriter()
    writer.emit({"seq": 1})
    writer.emit({"seq": 2})
    writer.close()

    chunks = await _collect_sse(writer)
    assert chunks[0] == f"data: {json.dumps({'seq': 1})}\n\n"
    assert chunks[1] == f"data: {json.dumps({'seq': 2})}\n\n"
    assert chunks[2] == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_close_produces_done():
    writer = StreamWriter()
    writer.close()
    chunks = await _collect_sse(writer)
    assert chunks == ["data: [DONE]\n\n"]


@pytest.mark.asyncio
async def test_emit_after_close_dropped():
    writer = StreamWriter()
    writer.close()
    writer.emit({"ignored": True})
    chunks = await _collect_sse(writer)
    assert chunks == ["data: [DONE]\n\n"]


def test_typed_helpers():
    w = StreamWriter()
    w.step_start("agent-a")
    w.token("agent-a", "tok")
    w.researching("agent-a", ["q1", "q2"])
    w.content("agent-a", "body")
    w.route("pat", "next_step")
    w.loop_iteration(2, 5)
    w.step_end("agent-a")
    w.error("agent-a", "oops")

    assert _drain_raw_events(w) == [
        {"type": "step_start", "agent": "agent-a"},
        {"type": "token", "agent": "agent-a", "token": "tok"},
        {"type": "researching", "agent": "agent-a", "queries": ["q1", "q2"]},
        {"type": "content", "agent": "agent-a", "content": "body"},
        {"type": "route", "matched": "pat", "next": "next_step"},
        {"type": "loop_iteration", "iteration": 2, "max": 5},
        {"type": "step_end", "agent": "agent-a"},
        {"type": "error", "agent": "agent-a", "message": "oops"},
    ]


@pytest.mark.asyncio
async def test_complete_closes_stream():
    writer = StreamWriter()
    writer.complete("final")

    chunks = await _collect_sse(writer)
    assert len(chunks) == 2
    assert json.loads(chunks[0].removeprefix("data: ").strip()) == {
        "type": "complete",
        "result": "final",
    }
    assert chunks[1] == "data: [DONE]\n\n"

    writer.emit({"after": "close"})
    with pytest.raises(asyncio.QueueEmpty):
        writer._queue.get_nowait()
