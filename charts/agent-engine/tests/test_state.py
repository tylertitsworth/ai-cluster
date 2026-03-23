"""Tests for engine.state.State and engine.state.CheckpointStore."""

import pytest

from engine.state import CheckpointStore, State


def test_state_add_messages():
    state = State("thread-1", {"cfg": True}, {"foo": "bar"})
    state.add_message({"role": "user", "content": "hello"})
    state.add_messages(
        [
            {"role": "assistant", "content": "hi"},
            {"role": "tool", "content": "ok"},
        ]
    )
    assert state.messages == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "tool", "content": "ok"},
    ]


def test_state_counters():
    state = State("t", {}, {})
    state.increment_counter("n")
    state.increment_counter("n")
    state.increment_counter("n")
    assert state.get_counter("n") == 3
    state.reset_counter("n")
    assert state.get_counter("n") == 0


def test_state_serialization_roundtrip():
    state = State("tid", {"snap": 1}, {"x": "y"})
    state.add_messages([{"role": "user", "content": "a"}])
    state.increment_counter("c")
    state.flow_position = ["step1", {"loop": 0}]

    data = state.to_dict()
    restored = State.from_dict(data)

    assert restored.thread_id == state.thread_id
    assert restored.messages == state.messages
    assert restored.params == state.params
    assert restored.counters == state.counters
    assert restored.flow_position == state.flow_position
    assert restored.config_snapshot == state.config_snapshot


@pytest.mark.asyncio
async def test_checkpoint_save_load(tmp_db):
    store = CheckpointStore(tmp_db)
    await store.init()
    original = State("thread-a", {"model": "m"}, {"temperature": 0.5})
    original.add_message({"role": "user", "content": "ping"})
    await store.save(original)

    loaded = await store.load("thread-a")
    assert loaded is not None
    assert loaded.thread_id == "thread-a"
    assert loaded.messages == [{"role": "user", "content": "ping"}]
    assert loaded.params == {"temperature": 0.5}
    assert loaded.config_snapshot == {"model": "m"}


@pytest.mark.asyncio
async def test_checkpoint_load_missing(tmp_db):
    store = CheckpointStore(tmp_db)
    await store.init()
    assert await store.load("nonexistent") is None


@pytest.mark.asyncio
async def test_checkpoint_delete(tmp_db):
    store = CheckpointStore(tmp_db)
    await store.init()
    state = State("to-delete", {}, {"k": "v"})
    await store.save(state)
    assert await store.load("to-delete") is not None

    await store.delete("to-delete")
    assert await store.load("to-delete") is None


@pytest.mark.asyncio
async def test_checkpoint_overwrite(tmp_db):
    store = CheckpointStore(tmp_db)
    await store.init()
    s1 = State("same-thread", {}, {})
    s1.messages = [{"content": "a"}]
    await store.save(s1)

    s2 = State("same-thread", {}, {})
    s2.messages = [{"content": "b"}]
    await store.save(s2)

    loaded = await store.load("same-thread")
    assert loaded is not None
    assert loaded.messages == [{"content": "b"}]
