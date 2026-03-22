"""Tests for StreamWriter event emission."""

import asyncio
import json

import pytest


class TestStreamWriter:
    @pytest.mark.asyncio
    async def test_emit_and_consume(self):
        from engine.stream import StreamWriter

        sw = StreamWriter()
        sw.emit({"type": "token", "agent": "writer", "token": "hello"})
        sw.close()

        events = []
        async for event_str in sw.events():
            events.append(event_str)

        assert len(events) == 2
        assert '"token"' in events[0]
        assert events[1] == "data: [DONE]\n\n"

    @pytest.mark.asyncio
    async def test_typed_helpers(self):
        from engine.stream import StreamWriter

        sw = StreamWriter()
        sw.step_start("investigator")
        sw.token("investigator", "Looking at the pods...")
        sw.researching("investigator", ["get pods -n monitoring"])
        sw.route("STATUS: FIXED", "end")
        sw.loop_iteration(2, 5)
        sw.content("writer", "Full section text")
        sw.error("executor", "Timed out")
        sw.complete("Final result")

        events = []
        async for event_str in sw.events():
            if event_str.startswith("data: [DONE]"):
                break
            data = json.loads(event_str.removeprefix("data: "))
            events.append(data)

        types = [e["type"] for e in events]
        assert types == [
            "step_start",
            "token",
            "researching",
            "route",
            "loop_iteration",
            "content",
            "error",
            "complete",
        ]

        assert events[0]["agent"] == "investigator"
        assert events[1]["token"] == "Looking at the pods..."
        assert events[2]["queries"] == ["get pods -n monitoring"]
        assert events[3]["matched"] == "STATUS: FIXED"
        assert events[4]["iteration"] == 2
        assert events[5]["content"] == "Full section text"
        assert events[6]["message"] == "Timed out"
        assert events[7]["result"] == "Final result"

    @pytest.mark.asyncio
    async def test_complete_closes_stream(self):
        from engine.stream import StreamWriter

        sw = StreamWriter()
        sw.complete("done")

        events = []
        async for event_str in sw.events():
            events.append(event_str)

        assert sw._closed
        assert events[-1] == "data: [DONE]\n\n"

    @pytest.mark.asyncio
    async def test_emit_after_close_is_dropped(self):
        from engine.stream import StreamWriter

        sw = StreamWriter()
        sw.close()
        sw.emit({"type": "token", "token": "should be dropped"})

        events = []
        async for event_str in sw.events():
            events.append(event_str)

        assert len(events) == 1  # only [DONE]
