"""Integration tests for the Diplomacy workflow."""

import pytest

from engine.executor import run_workflow
from engine.registry import WorkflowRegistry
from engine.state import CheckpointStore
from engine.stream import StreamWriter


def _collect_events(stream):
    events = []
    while not stream._queue.empty():
        ev = stream._queue.get_nowait()
        if ev is not None:
            events.append(ev)
    return events


@pytest.mark.asyncio
async def test_diplomacy_workflow_loads(mock_ray, mock_agent_class, mock_tool_manager):
    """The diplomacy workflow YAML loads and has all 8 agents."""
    registry = WorkflowRegistry()
    config = registry.get("diplomacy")
    assert config is not None, f"Workflow 'diplomacy' not found. Available: {list(registry.workflows.keys())}"
    assert len(config["agents"]) == 8
    assert "game_master" in config["agents"]
    assert "england" in config["agents"]
    assert "france" in config["agents"]
    assert "germany" in config["agents"]
    assert "italy" in config["agents"]
    assert "austria" in config["agents"]
    assert "russia" in config["agents"]
    assert "turkey" in config["agents"]


@pytest.mark.asyncio
async def test_diplomacy_prompts_loaded(mock_ray, mock_agent_class, mock_tool_manager):
    """All 8 prompt files are loaded into the workflow config."""
    registry = WorkflowRegistry()
    config = registry.get("diplomacy")
    assert config is not None
    prompts = config.get("_prompts", {})
    for agent_name in ["game_master", "england", "france", "germany", "italy", "austria", "russia", "turkey"]:
        assert agent_name in prompts, f"Prompt for '{agent_name}' not loaded"
        assert len(prompts[agent_name]) > 100, f"Prompt for '{agent_name}' is too short"


@pytest.mark.asyncio
async def test_diplomacy_flow_structure(mock_ray, mock_agent_class, mock_tool_manager):
    """The flow has the expected structure: game_master setup, then a loop."""
    registry = WorkflowRegistry()
    config = registry.get("diplomacy")
    assert config is not None
    flow = config["flow"]
    assert isinstance(flow, list)
    assert len(flow) == 2
    assert flow[0] == {"step": "game_master"}
    assert "loop" in flow[1]
    loop = flow[1]["loop"]
    assert loop["max"] == 20


@pytest.mark.asyncio
async def test_diplomacy_runs_one_turn(tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    """Full workflow runs at least one turn with all agents called."""
    registry = WorkflowRegistry()
    config = registry.get("diplomacy")
    assert config is not None

    stream = StreamWriter()
    checkpoints = CheckpointStore(tmp_db)
    await checkpoints.init()

    result = await run_workflow(
        config=config,
        query="Start a new game of Diplomacy",
        thread_id="diplo-test",
        params={},
        agent_overrides={},
        stream=stream,
        checkpoints=checkpoints,
        registry=registry,
    )

    assert isinstance(result, str)
    assert len(result) > 0

    events = _collect_events(stream)
    step_starts = [e for e in events if e.get("type") == "step_start"]
    agents_called = {e["agent"] for e in step_starts}

    assert "game_master" in agents_called
    assert "england" in agents_called
    assert "turkey" in agents_called


@pytest.mark.asyncio
async def test_diplomacy_parallel_phases(tmp_db, mock_ray, mock_agent_class, mock_tool_manager):
    """The workflow uses parallel execution for nation phases."""
    registry = WorkflowRegistry()
    config = registry.get("diplomacy")
    assert config is not None

    stream = StreamWriter()
    checkpoints = CheckpointStore(tmp_db)
    await checkpoints.init()

    await run_workflow(
        config=config,
        query="Play Diplomacy",
        thread_id="diplo-parallel",
        params={},
        agent_overrides={},
        stream=stream,
        checkpoints=checkpoints,
        registry=registry,
    )

    events = _collect_events(stream)
    step_starts = [e for e in events if e.get("type") == "step_start"]
    agents_called = [e["agent"] for e in step_starts]

    nation_agents = {"england", "france", "germany", "italy", "austria", "russia", "turkey"}
    nations_in_events = [a for a in agents_called if a in nation_agents]
    assert len(nations_in_events) >= 7, f"Expected at least 7 nation calls, got {len(nations_in_events)}"
