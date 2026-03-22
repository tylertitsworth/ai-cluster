"""Tests for State management and CheckpointStore."""

import pytest


class TestState:
    def test_create_and_serialize(self):
        from engine.state import State

        state = State("thread-1", {"name": "test"}, {"key": "val"})
        state.add_message({"role": "user", "content": "hello"})
        state.add_message({"role": "assistant", "content": "hi"})

        d = state.to_dict()
        assert d["thread_id"] == "thread-1"
        assert len(d["messages"]) == 2
        assert d["params"]["key"] == "val"

    def test_roundtrip_serialization(self):
        from engine.state import State

        original = State("thread-1", {"name": "test"}, {"x": 1})
        original.add_message({"role": "user", "content": "hello"})
        original.counters["loop_abc"] = 3
        original.flow_position = [0, 2, 1]

        restored = State.from_dict(original.to_dict())
        assert restored.thread_id == "thread-1"
        assert restored.messages == original.messages
        assert restored.counters == {"loop_abc": 3}
        assert restored.flow_position == [0, 2, 1]
        assert restored.config_snapshot == {"name": "test"}

    def test_counter_operations(self):
        from engine.state import State

        state = State("t", {}, {})
        assert state.get_counter("x") == 0
        state.increment_counter("x")
        assert state.get_counter("x") == 1
        state.increment_counter("x")
        assert state.get_counter("x") == 2
        state.reset_counter("x")
        assert state.get_counter("x") == 0


class TestCheckpointStore:
    @pytest.mark.asyncio
    async def test_save_and_load(self, tmp_db):
        from engine.state import CheckpointStore, State

        store = CheckpointStore(tmp_db)
        await store.init()

        state = State("thread-1", {"name": "test"}, {})
        state.add_message({"role": "user", "content": "hello"})
        await store.save(state)

        loaded = await store.load("thread-1")
        assert loaded is not None
        assert loaded.thread_id == "thread-1"
        assert loaded.messages == [{"role": "user", "content": "hello"}]

    @pytest.mark.asyncio
    async def test_load_missing_returns_none(self, tmp_db):
        from engine.state import CheckpointStore

        store = CheckpointStore(tmp_db)
        await store.init()

        result = await store.load("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_overwrites(self, tmp_db):
        from engine.state import CheckpointStore, State

        store = CheckpointStore(tmp_db)
        await store.init()

        state = State("thread-1", {}, {})
        state.add_message({"role": "user", "content": "first"})
        await store.save(state)

        state.add_message({"role": "assistant", "content": "second"})
        await store.save(state)

        loaded = await store.load("thread-1")
        assert len(loaded.messages) == 2

    @pytest.mark.asyncio
    async def test_delete(self, tmp_db):
        from engine.state import CheckpointStore, State

        store = CheckpointStore(tmp_db)
        await store.init()

        state = State("thread-1", {}, {})
        await store.save(state)
        await store.delete("thread-1")

        result = await store.load("thread-1")
        assert result is None
