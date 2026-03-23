"""Tests for the core execution engine primitives."""

import asyncio
import json

import pytest

from engine.executor import (
    _ExecutionContext,
    _execute,
    _execute_loop,
    _execute_parallel,
    _execute_race,
    _execute_ralph,
    _execute_review,
    _execute_route,
    _execute_sequence,
    _execute_step,
    _last_assistant_content,
    run_workflow,
)
from engine.state import CheckpointStore, State
from engine.stream import StreamWriter


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _make_ctx(config, tmp_db, initial_messages=None, params=None):
    from engine.registry import WorkflowRegistry

    state = State("test-thread", config, params or {})
    if initial_messages:
        state.add_messages(initial_messages)
    stream = StreamWriter()
    checkpoints = CheckpointStore(tmp_db)
    await checkpoints.init()
    registry = WorkflowRegistry.__new__(WorkflowRegistry)
    registry.workflows = {config["name"]: config}

    ctx = _ExecutionContext(
        config=config,
        state=state,
        stream=stream,
        checkpoints=checkpoints,
        agent_overrides={},
        registry=registry,
    )
    from tests.conftest import MockToolManager
    ctx.tool_manager = MockToolManager(config.get("tools", {}))
    return ctx


def _collect_stream_events(stream):
    events = []
    while not stream._queue.empty():
        ev = stream._queue.get_nowait()
        if ev is not None:
            events.append(ev)
    return events


# ---------------------------------------------------------------------------
# Sequence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sequence_executes_in_order(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(sample_workflow_config, tmp_db, [{"role": "user", "content": "hello"}])
    flow = [{"step": "agent_a"}, {"step": "agent_b"}]

    await _execute_sequence(flow, ctx, path=[])

    assistant_msgs = [m for m in ctx.state.messages if m.get("role") == "assistant"]
    assert len(assistant_msgs) >= 2


@pytest.mark.asyncio
async def test_sequence_end_breaks(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(sample_workflow_config, tmp_db, [{"role": "user", "content": "hello"}])
    flow = [
        {"step": "agent_a"},
        {"route": {"Response from agent": "end", "default": "continue"}},
        {"step": "agent_b"},
    ]

    result = await _execute_sequence(flow, ctx, path=[])
    assert result == "end"

    assistant_msgs = [m for m in ctx.state.messages if m.get("role") == "assistant"]
    assert len(assistant_msgs) == 1


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_step_calls_agent(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(sample_workflow_config, tmp_db, [{"role": "user", "content": "test"}])

    await _execute_step({"step": "agent_a"}, ctx)

    assistant_msgs = [m for m in ctx.state.messages if m.get("role") == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0]["content"] is not None


@pytest.mark.asyncio
async def test_step_tool_loop(service_debugger_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(service_debugger_config, tmp_db, [{"role": "user", "content": "debug"}])

    await _execute_step({"step": "investigator", "tool_loop": 10}, ctx)

    tool_msgs = [m for m in ctx.state.messages if m.get("role") == "tool"]
    assert len(tool_msgs) >= 1

    assistant_msgs = [m for m in ctx.state.messages if m.get("role") == "assistant"]
    assert len(assistant_msgs) >= 2


@pytest.mark.asyncio
async def test_step_parallel_mode(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(sample_workflow_config, tmp_db, [{"role": "user", "content": "test"}])

    await _execute_step({"step": "agent_a", "_parallel": True}, ctx)

    events = _collect_stream_events(ctx.stream)
    content_events = [e for e in events if e.get("type") == "content"]
    assert len(content_events) >= 1


# ---------------------------------------------------------------------------
# Loop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_loop_max_iterations(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(sample_workflow_config, tmp_db, [{"role": "user", "content": "test"}])
    loop_node = {"max": 3, "steps": [{"step": "agent_a"}]}

    await _execute_loop(loop_node, ctx, path=[])

    events = _collect_stream_events(ctx.stream)
    loop_events = [e for e in events if e.get("type") == "loop_iteration"]
    assert len(loop_events) == 3


@pytest.mark.asyncio
async def test_loop_end_breaks_early(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(sample_workflow_config, tmp_db, [{"role": "user", "content": "test"}])
    loop_node = {
        "max": 10,
        "steps": [
            {"step": "agent_a"},
            {"route": {"Response from agent": "end", "default": "continue"}},
        ],
    }

    await _execute_loop(loop_node, ctx, path=[])

    events = _collect_stream_events(ctx.stream)
    loop_events = [e for e in events if e.get("type") == "loop_iteration"]
    assert len(loop_events) == 1


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_matches_pattern(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(sample_workflow_config, tmp_db)
    ctx.state.add_message({"role": "assistant", "content": "All done. STATUS: FIXED"})

    result = await _execute_route({"STATUS: FIXED": "end", "default": "continue"}, ctx)
    assert result == "end"


@pytest.mark.asyncio
async def test_route_default(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(sample_workflow_config, tmp_db)
    ctx.state.add_message({"role": "assistant", "content": "Still working"})

    result = await _execute_route({"STATUS: FIXED": "end", "default": "continue"}, ctx)
    assert result is None


@pytest.mark.asyncio
async def test_route_default_end(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(sample_workflow_config, tmp_db)
    ctx.state.add_message({"role": "assistant", "content": "unrelated"})

    result = await _execute_route({"STATUS: FIXED": "end", "default": "end"}, ctx)
    assert result == "end"


@pytest.mark.asyncio
async def test_route_emits_event(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(sample_workflow_config, tmp_db)
    ctx.state.add_message({"role": "assistant", "content": "STATUS: FIXED"})

    await _execute_route({"STATUS: FIXED": "end"}, ctx)

    events = _collect_stream_events(ctx.stream)
    route_events = [e for e in events if e.get("type") == "route"]
    assert len(route_events) == 1
    assert route_events[0]["matched"] == "STATUS: FIXED"


# ---------------------------------------------------------------------------
# Parallel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_fan_out(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    config = {**sample_workflow_config}
    ctx = await _make_ctx(config, tmp_db, [{"role": "user", "content": "test"}])

    parallel_node = {"agent": "agent_a", "count": 2, "resolve": "concatenate"}
    await _execute_parallel(parallel_node, ctx)

    last = _last_assistant_content(ctx.state)
    assert len(last) > 0


@pytest.mark.asyncio
async def test_parallel_count_from_params(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(sample_workflow_config, tmp_db, [{"role": "user", "content": "test"}], params={"n": 2})

    parallel_node = {"agent": "agent_a", "count": "{n}", "resolve": "concatenate"}
    await _execute_parallel(parallel_node, ctx)

    last = _last_assistant_content(ctx.state)
    assert len(last) > 0


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_review_approved(service_debugger_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(service_debugger_config, tmp_db, [
        {"role": "user", "content": "test"},
        {"role": "assistant", "content": "proposed fix"},
    ])

    result = await _execute_review(
        {"reviewer": "guardrails", "reject": "VERDICT: UNSAFE", "max_retries": 2},
        ctx,
    )
    assert result is None

    events = _collect_stream_events(ctx.stream)
    route_events = [e for e in events if e.get("type") == "route"]
    assert any("approved" in e.get("matched", "") for e in route_events)


@pytest.mark.asyncio
async def test_review_rejected(service_debugger_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(service_debugger_config, tmp_db, [
        {"role": "user", "content": "test"},
        {"role": "assistant", "content": "proposed fix"},
    ])

    guardrails_agent = ctx.get_or_create_agent("guardrails")
    guardrails_agent._force_unsafe = 1

    result = await _execute_review(
        {"reviewer": "guardrails", "reject": "VERDICT: UNSAFE", "max_retries": 2},
        ctx,
    )
    assert result is None
    assert ctx.state.get_counter("review_guardrails") == 1


@pytest.mark.asyncio
async def test_review_max_retries_exceeded(service_debugger_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(service_debugger_config, tmp_db, [
        {"role": "user", "content": "test"},
        {"role": "assistant", "content": "proposed fix"},
    ])

    ctx.state.counters["review_guardrails"] = 2
    guardrails_agent = ctx.get_or_create_agent("guardrails")
    guardrails_agent._force_unsafe = 1

    result = await _execute_review(
        {"reviewer": "guardrails", "reject": "VERDICT: UNSAFE", "max_retries": 2},
        ctx,
    )
    assert result == "end"


# ---------------------------------------------------------------------------
# Race
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_race_runs_branches(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    config = {**sample_workflow_config}
    config["agents"]["_judge"] = {"provider": "test", "prompt": "_judge"}
    config["_prompts"]["_judge"] = "You are a judge."

    ctx = await _make_ctx(config, tmp_db, [{"role": "user", "content": "test"}])

    race_node = {
        "count": 2,
        "steps": [{"step": "agent_a"}],
        "resolve": {"strategy": "pick", "judge": "_judge", "criteria": "best"},
    }
    await _execute_race(race_node, ctx)

    last = _last_assistant_content(ctx.state)
    assert len(last) > 0


# ---------------------------------------------------------------------------
# Ralph
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ralph_done_pattern(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    config = {**sample_workflow_config}
    config["agents"]["done_agent"] = {"provider": "test", "prompt": "done_agent"}
    config["_prompts"]["done_agent"] = "You always say DONE."

    ctx = await _make_ctx(config, tmp_db, [{"role": "user", "content": "do tasks"}])

    ralph_node = {"max": 5, "steps": [{"step": "done_agent"}], "done": "Response from agent"}

    await _execute_ralph(ralph_node, ctx, path=[])

    events = _collect_stream_events(ctx.stream)
    loop_events = [e for e in events if e.get("type") == "loop_iteration"]
    assert len(loop_events) == 1


@pytest.mark.asyncio
async def test_ralph_max_tasks(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(sample_workflow_config, tmp_db, [{"role": "user", "content": "tasks"}])

    ralph_node = {"max": 3, "steps": [{"step": "agent_a"}], "done": "NEVER_MATCH"}
    await _execute_ralph(ralph_node, ctx, path=[])

    events = _collect_stream_events(ctx.stream)
    loop_events = [e for e in events if e.get("type") == "loop_iteration"]
    assert len(loop_events) == 3


# ---------------------------------------------------------------------------
# Flow position
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flow_position_tracked(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(sample_workflow_config, tmp_db, [{"role": "user", "content": "test"}])
    flow = [{"step": "agent_a"}, {"step": "agent_b"}]

    await _execute_sequence(flow, ctx, path=[0])

    assert len(ctx.state.flow_position) > 0


@pytest.mark.asyncio
async def test_resume_skips_completed(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    ctx = await _make_ctx(sample_workflow_config, tmp_db, [
        {"role": "user", "content": "test"},
        {"role": "assistant", "content": "already done step 0"},
    ])

    flow = [{"step": "agent_a"}, {"step": "agent_b"}]
    await _execute_sequence(flow, ctx, path=[], resume_from=[1])

    assistant_msgs = [m for m in ctx.state.messages if m.get("role") == "assistant"]
    assert len(assistant_msgs) == 2


# ---------------------------------------------------------------------------
# _parse_agent_sections helper
# ---------------------------------------------------------------------------

def test_parse_agent_sections_basic():
    """Parses labeled sections and returns per-agent content."""
    from engine.executor import _parse_agent_sections
    text = "[AGENT_A]\nTask for A\n\n[AGENT_B]\nTask for B\n\n[AGENT_C]\nTask for C"
    sections = _parse_agent_sections(text, ["agent_a", "agent_b", "agent_c"])
    assert sections["agent_a"] == "Task for A"
    assert sections["agent_b"] == "Task for B"
    assert sections["agent_c"] == "Task for C"


def test_parse_agent_sections_missing_agent():
    """Agents with no matching section are omitted from the result."""
    from engine.executor import _parse_agent_sections
    text = "[AGENT_A]\nOnly A gets context"
    sections = _parse_agent_sections(text, ["agent_a", "agent_b"])
    assert "agent_a" in sections
    assert "agent_b" not in sections


def test_parse_agent_sections_empty_text():
    """Empty text returns empty dict."""
    from engine.executor import _parse_agent_sections
    sections = _parse_agent_sections("", ["agent_a"])
    assert sections == {}


# ---------------------------------------------------------------------------
# Parallel: agents list + inject_context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_agents_list(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    """parallel with agents: [agent_a, agent_b] runs 2 different agents, one per branch."""
    ctx = await _make_ctx(sample_workflow_config, tmp_db, [{"role": "user", "content": "test"}])
    parallel_node = {"agents": ["agent_a", "agent_b"], "resolve": "concatenate"}
    await _execute_parallel(parallel_node, ctx)
    events = _collect_stream_events(ctx.stream)
    step_starts = [e for e in events if e.get("type") == "step_start"]
    agents_started = {e["agent"] for e in step_starts}
    assert "agent_a" in agents_started, f"agent_a not started, got: {agents_started}"
    assert "agent_b" in agents_started, f"agent_b not started, got: {agents_started}"


@pytest.mark.asyncio
async def test_parallel_inject_context(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    """inject_context routes [AGENT_NAME] sections to the matching branch."""
    ctx = await _make_ctx(sample_workflow_config, tmp_db, [
        {"role": "user", "content": "test"},
        {"role": "assistant", "content": "[AGENT_A]\nPrivate task for A\n\n[AGENT_B]\nPrivate task for B"},
    ])
    parallel_node = {"agents": ["agent_a", "agent_b"], "inject_context": True, "resolve": "concatenate"}
    await _execute_parallel(parallel_node, ctx)
    last = _last_assistant_content(ctx.state)
    assert len(last) > 0


@pytest.mark.asyncio
async def test_parallel_agents_list_with_single_agent_fallback(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    """When agents is not set, falls back to agent + count (existing behavior)."""
    ctx = await _make_ctx(sample_workflow_config, tmp_db, [{"role": "user", "content": "test"}])
    parallel_node = {"agent": "agent_a", "count": 2, "resolve": "concatenate"}
    await _execute_parallel(parallel_node, ctx)
    last = _last_assistant_content(ctx.state)
    assert len(last) > 0


# ---------------------------------------------------------------------------
# run_workflow (integration)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_workflow_basic(sample_workflow_config, tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    from engine.registry import WorkflowRegistry

    stream = StreamWriter()
    checkpoints = CheckpointStore(tmp_db)
    await checkpoints.init()

    registry = WorkflowRegistry.__new__(WorkflowRegistry)
    registry.workflows = {sample_workflow_config["name"]: sample_workflow_config}

    result = await run_workflow(
        config=sample_workflow_config,
        query="test query",
        thread_id="t1",
        params={},
        agent_overrides={},
        stream=stream,
        checkpoints=checkpoints,
        registry=registry,
    )

    assert isinstance(result, str)
    assert len(result) > 0
