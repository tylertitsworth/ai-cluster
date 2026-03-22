"""Core execution engine — interprets YAML flow definitions.

Recursively evaluates a flow tree composed of 6 primitives:
step, workflow, sequence (implicit list), loop, parallel, route.

Plus 3 meta-pattern shorthands: review, race, ralph.
"""

import asyncio
import json
import logging
import re
from copy import deepcopy
from hashlib import md5

import ray

from engine.agent import Agent
from engine.providers import resolve_agent_config
from engine.registry import WorkflowRegistry
from engine.state import CheckpointStore, State
from engine.stream import StreamWriter
from engine.tools import ToolManager

logger = logging.getLogger(__name__)

ACTOR_TIMEOUT = 300
_SYNTHESIZE_MSG = (
    "You have reached the tool call limit. Do NOT make any more tool calls. "
    "Using the information you already gathered, write your analysis now."
)


# ------------------------------------------------------------------
# Public entry points
# ------------------------------------------------------------------


async def run_workflow(
    config: dict,
    query: str,
    thread_id: str,
    params: dict,
    agent_overrides: dict,
    stream: StreamWriter,
    checkpoints: CheckpointStore,
    registry: WorkflowRegistry,
) -> str:
    """Execute a workflow from start to finish."""
    snapshot = deepcopy(config)
    state = State(thread_id, snapshot, params)
    state.add_message({"role": "user", "content": query})

    ctx = _ExecutionContext(
        config=snapshot,
        state=state,
        stream=stream,
        checkpoints=checkpoints,
        agent_overrides=agent_overrides,
        registry=registry,
    )

    try:
        await ctx.setup_placement_group()
        await ctx.setup_tools()
        await _execute(snapshot["flow"], ctx, path=[])
    finally:
        await ctx.cleanup()

    result = _last_assistant_content(state)
    stream.complete(result)
    await checkpoints.save(state)
    return result


async def resume_workflow(
    state: State,
    stream: StreamWriter,
    checkpoints: CheckpointStore,
    registry: WorkflowRegistry,
) -> str:
    """Resume a workflow from a checkpoint."""
    config = state.config_snapshot

    ctx = _ExecutionContext(
        config=config,
        state=state,
        stream=stream,
        checkpoints=checkpoints,
        agent_overrides={},
        registry=registry,
    )

    try:
        await ctx.setup_placement_group()
        await ctx.setup_tools()

        resume_pos = list(state.flow_position)
        await _execute(config["flow"], ctx, path=[], resume_from=resume_pos)
    finally:
        await ctx.cleanup()

    result = _last_assistant_content(state)
    stream.complete(result)
    await checkpoints.save(state)
    return result


# ------------------------------------------------------------------
# Execution context — bundles dependencies for recursive execute
# ------------------------------------------------------------------


class _ExecutionContext:
    """Holds all runtime state needed during execution."""

    def __init__(
        self,
        config: dict,
        state: State,
        stream: StreamWriter,
        checkpoints: CheckpointStore,
        agent_overrides: dict,
        registry: WorkflowRegistry,
    ):
        self.config = config
        self.state = state
        self.stream = stream
        self.checkpoints = checkpoints
        self.agent_overrides = agent_overrides
        self.registry = registry
        self.tool_manager: ToolManager | None = None
        self.agents: dict[str, ray.ObjectRef] = {}
        self.placement_group = None

    async def setup_tools(self):
        tools_config = self.config.get("tools", {})
        if tools_config:
            self.tool_manager = ToolManager(tools_config)
            await self.tool_manager.connect_all()

    async def setup_placement_group(self, timeout: int = 120):
        """Create a placement group for per-workflow pod isolation.

        Blocks until a worker pod with the right tier resources is available.
        If no worker can satisfy the request within the timeout, the placement
        group is removed and a RuntimeError is raised -- we do NOT fall back
        to unsandboxed scheduling.
        """
        tier = self.config.get("tier", "default")
        tier_resource_key = f"tier_{tier.replace('-', '_')}"

            pg = ray.util.placement_group(
                bundles=[{tier_resource_key: 1, "CPU": 1}],
                strategy="STRICT_PACK",
            )
        logger.info("Waiting for placement group on tier '%s'...", tier)

        loop = asyncio.get_event_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, lambda: ray.get(pg.ready(), timeout=timeout)),
                timeout=timeout + 5,
            )
        except Exception:
            try:
                ray.util.remove_placement_group(pg)
            except Exception:
                pass
            raise RuntimeError(
                f"No worker available for tier '{tier}' within {timeout}s. "
                f"Ensure the '{tier}' worker group has minReplicas >= 1 or "
                f"the autoscaler can provision a worker in time."
            )

        self.placement_group = pg
        logger.info("Placement group ready for tier '%s'", tier)

    def get_tool_schemas_for_agent(self, agent_name: str) -> list[dict]:
        """Return only the tool schemas that this agent is authorized to use."""
        agent_cfg = self.config.get("agents", {}).get(agent_name, {})
        tool_refs = agent_cfg.get("tools", [])
        if not tool_refs or not self.tool_manager:
            return []
        allowed_fn_names = self.tool_manager.get_function_names_for_groups(tool_refs)
        all_schemas = self.tool_manager.get_schemas()
        return [s for s in all_schemas if s["function"]["name"] in allowed_fn_names]

    def get_or_create_agent(self, agent_name: str) -> ray.ObjectRef:
        if agent_name in self.agents:
            return self.agents[agent_name]

        agent_cfg = resolve_agent_config(
            agent_name, self.config, self.agent_overrides
        )
        tool_schemas = self.get_tool_schemas_for_agent(agent_name)

        options = {}
        if self.placement_group:
            options["placement_group"] = self.placement_group

        actor = Agent.options(**options).remote(
            agent_cfg["provider_config"],
            agent_cfg["system_prompt"],
            tool_schemas or None,
        )
        self.agents[agent_name] = actor
        return actor

    async def cleanup(self):
        for name, actor in self.agents.items():
            try:
                ray.kill(actor)
            except Exception:
                logger.warning("Failed to kill actor %s", name)
        self.agents.clear()
        if self.placement_group:
            try:
                ray.util.remove_placement_group(self.placement_group)
            except Exception:
                logger.warning("Failed to remove placement group")
            self.placement_group = None
        if self.tool_manager:
            await self.tool_manager.close()


# ------------------------------------------------------------------
# Recursive flow interpreter with flow_position tracking (C6)
# ------------------------------------------------------------------


async def _execute(
    node,
    ctx: _ExecutionContext,
    path: list,
    resume_from: list | None = None,
) -> str | None:
    """Execute a flow node. Returns "end" to break out of loops, else None.

    path:        current position in the flow tree (for checkpoint tracking)
    resume_from: if set, skip nodes until we reach this position
    """
    if isinstance(node, list):
        return await _execute_sequence(node, ctx, path, resume_from)

    if isinstance(node, dict):
        if "step" in node:
            return await _execute_step(node, ctx)
        if "workflow" in node:
            return await _execute_workflow_ref(node, ctx, path=path, resume_from=resume_from)
        if "loop" in node:
            return await _execute_loop(node["loop"], ctx, path, resume_from)
        if "route" in node:
            return await _execute_route(node["route"], ctx)
        if "parallel" in node:
            return await _execute_parallel(node["parallel"], ctx)
        if "review" in node:
            return await _execute_review(node["review"], ctx)
        if "race" in node:
            return await _execute_race(node["race"], ctx)
        if "ralph" in node:
            return await _execute_ralph(node["ralph"], ctx, path, resume_from)

        if "steps" in node and "max" in node:
            return await _execute_loop(node, ctx, path, resume_from)

    logger.error("Unknown flow node type: %s", node)
    return None


async def _execute_sequence(
    steps: list,
    ctx: _ExecutionContext,
    path: list,
    resume_from: list | None = None,
) -> str | None:
    for i, step in enumerate(steps):
        step_path = path + [i]

        if resume_from and len(resume_from) > len(path):
            target_idx = resume_from[len(path)]
            if i < target_idx:
                continue

        ctx.state.flow_position = step_path
        result = await _execute(step, ctx, step_path, resume_from)
        if result == "end":
            return "end"
        await ctx.checkpoints.save(ctx.state)
    return None


# ------------------------------------------------------------------
# step — call an agent with optional tool loop
# ------------------------------------------------------------------


async def _execute_step(node: dict, ctx: _ExecutionContext) -> str | None:
    agent_name = node["step"]
    tool_loop_max = node.get("tool_loop", 0)
    parallel = node.get("_parallel", False)

    actor = ctx.get_or_create_agent(agent_name)
    ctx.stream.step_start(agent_name)

    messages = ctx.state.messages

    for round_num in range(tool_loop_max + 1):
        if parallel:
            response = await _call_agent_blocking(actor, messages)
        else:
            response = await _call_agent_streaming(actor, messages, agent_name, ctx.stream)

        ctx.state.add_message(response)

        tool_calls = response.get("tool_calls")
        if not tool_calls:
            break

        queries = _summarize_tool_calls(tool_calls)
        ctx.stream.researching(agent_name, queries)

        if ctx.tool_manager:
            tool_results = await ctx.tool_manager.execute(tool_calls)
        else:
            tool_results = [
                {"role": "tool", "tool_call_id": tc.get("id", ""), "content": "No tools configured"}
                for tc in tool_calls
            ]
        ctx.state.add_messages(tool_results)
        messages = ctx.state.messages

        if round_num == tool_loop_max - 1 and tool_loop_max > 0:
            ctx.state.add_message({"role": "user", "content": _SYNTHESIZE_MSG})

    if parallel and response.get("content"):
        ctx.stream.content(agent_name, response["content"])

    ctx.stream.step_end(agent_name)
    await ctx.checkpoints.save(ctx.state)
    return None


async def _call_agent_blocking(actor, messages: list[dict]) -> dict:
    """Call agent and wait for the complete response."""
    response = await asyncio.wait_for(
        actor.execute.remote(messages),
        timeout=ACTOR_TIMEOUT,
    )
    return response


async def _call_agent_streaming(
    actor, messages: list[dict], agent_name: str, stream: StreamWriter
) -> dict:
    """Stream tokens from agent, return the complete accumulated message."""
    final_message = None
    async for chunk_ref in actor.stream_execute.remote(messages):
        chunk = await asyncio.wait_for(chunk_ref, timeout=ACTOR_TIMEOUT)
        if chunk.get("type") == "delta" and chunk.get("content"):
            text = chunk["content"]
            text = _strip_think_streaming(text)
            if text:
                stream.token(agent_name, text)
        elif chunk.get("type") == "message":
            final_message = chunk

    if final_message is None:
        return {"role": "assistant", "content": "ERROR: No response from agent", "tool_calls": None}

    msg = {
        "role": final_message.get("role", "assistant"),
        "content": final_message.get("content"),
    }
    if final_message.get("tool_calls"):
        msg["tool_calls"] = final_message["tool_calls"]
    return msg


# ------------------------------------------------------------------
# workflow — invoke another registered workflow as a nested step
# ------------------------------------------------------------------


async def _execute_workflow_ref(
    node: dict,
    ctx: _ExecutionContext,
    path: list | None = None,
    resume_from: list | None = None,
) -> str | None:
    workflow_name = node["workflow"]
    nested_config = ctx.registry.get(workflow_name)
    if not nested_config:
        ctx.stream.error("system", f"Unknown nested workflow: {workflow_name}")
        return None

    nested_snapshot = deepcopy(nested_config)
    original_config = ctx.config
    ctx.config = nested_snapshot

    try:
        await _execute(nested_snapshot["flow"], ctx, path=path or [], resume_from=resume_from)
    finally:
        ctx.config = original_config

    return None


# ------------------------------------------------------------------
# loop — repeat steps up to max times
# ------------------------------------------------------------------


async def _execute_loop(
    node: dict,
    ctx: _ExecutionContext,
    path: list,
    resume_from: list | None = None,
) -> str | None:
    max_iterations = node.get("max", node.get("count", 10))
    steps = node.get("steps", [])
    counter_name = _stable_counter_name("loop", node)

    start_iter = 0
    if resume_from and len(resume_from) > len(path):
        start_iter = resume_from[len(path)]

    for i in range(start_iter, max_iterations):
        ctx.state.counters[counter_name] = i
        ctx.stream.loop_iteration(i + 1, max_iterations)

        iter_path = path + [i]
        ctx.state.flow_position = iter_path

        inner_resume = resume_from if (resume_from and i == start_iter) else None
        result = await _execute_sequence(steps, ctx, iter_path, inner_resume)
        if result == "end":
            return None
        await ctx.checkpoints.save(ctx.state)

    return None


# ------------------------------------------------------------------
# route — branch on text matches in the last assistant message
# ------------------------------------------------------------------


async def _execute_route(routes: dict, ctx: _ExecutionContext) -> str | None:
    last_content = _last_assistant_content(ctx.state)

    for pattern, target in routes.items():
        if pattern == "default":
            continue
        if pattern in last_content:
            ctx.stream.route(pattern, target)
            if target == "end":
                return "end"
            return None

    default = routes.get("default", "continue")
    ctx.stream.route("default", default)
    if default == "end":
        return "end"
    return None


# ------------------------------------------------------------------
# parallel — fan-out agents or workflows, resolve results
# ------------------------------------------------------------------


async def _execute_parallel(node: dict, ctx: _ExecutionContext) -> str | None:
    agent_name = node.get("agent")
    count = _resolve_count(node.get("count", 1), ctx.state.params)
    resolve_strategy = node.get("resolve", "concatenate")
    tool_loop = node.get("tool_loop", 0)

    isolation = ctx.config.get("isolation", "per-invocation")
    branch_contexts: list[_ExecutionContext] = []

    async def run_branch(index: int):
        branch_state = State(
            ctx.state.thread_id,
            ctx.state.config_snapshot,
            ctx.state.params,
        )
        branch_state.messages = list(ctx.state.messages)

        branch_ctx = _ExecutionContext(
            config=ctx.config,
            state=branch_state,
            stream=ctx.stream,
            checkpoints=ctx.checkpoints,
            agent_overrides=ctx.agent_overrides,
            registry=ctx.registry,
        )
        branch_ctx.tool_manager = ctx.tool_manager
        branch_contexts.append(branch_ctx)

        if isolation == "per-branch":
            await branch_ctx.setup_placement_group()
        else:
            branch_ctx.placement_group = ctx.placement_group

        cfg = resolve_agent_config(agent_name, ctx.config, ctx.agent_overrides)
        tool_schemas = ctx.get_tool_schemas_for_agent(agent_name)
        options = {}
        if branch_ctx.placement_group:
            options["placement_group"] = branch_ctx.placement_group
        actor = Agent.options(**options).remote(
            cfg["provider_config"], cfg["system_prompt"], tool_schemas or None,
        )
        branch_ctx.agents[agent_name] = actor

        await _execute_step(
            {"step": agent_name, "tool_loop": tool_loop, "_parallel": True},
            branch_ctx,
        )
        return _last_assistant_content(branch_state)

    try:
        results = await asyncio.gather(
            *[run_branch(i) for i in range(count)],
            return_exceptions=True,
        )
    finally:
        for bctx in branch_contexts:
            for name, actor in bctx.agents.items():
                try:
                    ray.kill(actor)
                except Exception:
                    pass
            bctx.agents.clear()
            if isolation == "per-branch" and bctx.placement_group:
                try:
                    ray.util.remove_placement_group(bctx.placement_group)
                except Exception:
                    pass

    parts = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.error("Parallel branch %d failed: %s", i, r)
        elif r:
            parts.append(r)

    if resolve_strategy == "pick" and len(parts) > 1:
        resolve_config = node.get("resolve_config", {})
        judge_name = resolve_config.get("judge")
        criteria = resolve_config.get("criteria", "best overall quality")
        if judge_name:
            numbered = "\n\n".join(f"--- Branch {i+1} ---\n{b}" for i, b in enumerate(parts))
            ctx.state.add_message({"role": "user", "content": (
                f"You are judging {len(parts)} responses. Criteria: {criteria}\n\n"
                f"{numbered}\n\nSelect the best and reproduce it in full."
            )})
            await _execute_step({"step": judge_name}, ctx)
            return None
    elif resolve_strategy == "merge" and len(parts) > 1:
        resolve_config = node.get("resolve_config", {})
        judge_name = resolve_config.get("judge")
        criteria = resolve_config.get("criteria", "synthesize the best elements")
        if judge_name:
            numbered = "\n\n".join(f"--- Branch {i+1} ---\n{b}" for i, b in enumerate(parts))
            ctx.state.add_message({"role": "user", "content": (
                f"Synthesize {len(parts)} responses into one. Criteria: {criteria}\n\n"
                f"{numbered}\n\nProduce a single merged output."
            )})
            await _execute_step({"step": judge_name}, ctx)
            return None

    combined = "\n\n".join(parts) if parts else "All branches failed to produce content."
    ctx.state.add_message({"role": "assistant", "content": combined})
    return None


# ------------------------------------------------------------------
# review — reviewer -> gate, returns "retry" to re-run preceding step
# ------------------------------------------------------------------


async def _execute_review(node: dict, ctx: _ExecutionContext) -> str | None:
    """Review gate. Returns None to continue, "end" on max retries exceeded.

    On rejection (below max retries), returns None so the surrounding loop
    re-runs the preceding step. On max retries exceeded, returns "end" to
    break the loop entirely. On approval, returns None.
    """
    reviewer_name = node.get("reviewer")
    reject_pattern = node.get("reject", "")
    max_retries = node.get("max_retries", 2)

    if not reviewer_name:
        logger.error("Review node missing 'reviewer' field")
        return None

    actor = ctx.get_or_create_agent(reviewer_name)
    ctx.stream.step_start(reviewer_name)

    response = await _call_agent_streaming(
        actor, ctx.state.messages, reviewer_name, ctx.stream
    )
    ctx.state.add_message(response)
    ctx.stream.step_end(reviewer_name)

    content = response.get("content", "")
    if reject_pattern and reject_pattern in content:
        retries = ctx.state.get_counter(f"review_{reviewer_name}")
        if retries >= max_retries:
            ctx.stream.route(reject_pattern, "max_retries_exceeded")
            return "end"
        ctx.state.increment_counter(f"review_{reviewer_name}")
        ctx.stream.route(reject_pattern, "retry")
        return None

    ctx.stream.route("approved", "continue")
    return None


# ------------------------------------------------------------------
# race — run N copies in parallel, judge results
# ------------------------------------------------------------------


async def _execute_race(node: dict, ctx: _ExecutionContext) -> str | None:
    count = node.get("count", 3)
    steps = node.get("steps", node.get("work", []))
    isolation = ctx.config.get("isolation", "per-invocation")
    branch_contexts: list[_ExecutionContext] = []

    async def run_race_branch(index: int):
        branch_state = State(
            ctx.state.thread_id,
            ctx.state.config_snapshot,
            ctx.state.params,
        )
        branch_state.messages = list(ctx.state.messages)

        silent_stream = StreamWriter()
        branch_ctx = _ExecutionContext(
            config=ctx.config,
            state=branch_state,
            stream=silent_stream,
            checkpoints=ctx.checkpoints,
            agent_overrides=ctx.agent_overrides,
            registry=ctx.registry,
        )
        branch_ctx.tool_manager = ctx.tool_manager
        branch_contexts.append(branch_ctx)

        if isolation == "per-branch":
            await branch_ctx.setup_placement_group()
        else:
            branch_ctx.placement_group = ctx.placement_group

        await _execute(steps, branch_ctx, path=[])
        silent_stream.close()
        return _last_assistant_content(branch_state)

    try:
        results = await asyncio.gather(
            *[run_race_branch(i) for i in range(count)],
            return_exceptions=True,
        )
    finally:
        parent_actor_ids = {id(a) for a in ctx.agents.values()}
        for bctx in branch_contexts:
            for name, actor in bctx.agents.items():
                if id(actor) not in parent_actor_ids:
                    try:
                        ray.kill(actor)
                    except Exception:
                        pass
            bctx.agents.clear()
            if isolation == "per-branch" and bctx.placement_group:
                try:
                    ray.util.remove_placement_group(bctx.placement_group)
                except Exception:
                    pass

    branches = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.error("Race branch %d failed: %s", i, r)
        elif r:
            branches.append(r)

    resolve_config = node.get("resolve", {})
    strategy = resolve_config.get("strategy", "pick") if isinstance(resolve_config, dict) else "pick"
    judge_name = resolve_config.get("judge") if isinstance(resolve_config, dict) else None
    criteria = resolve_config.get("criteria", "best overall quality") if isinstance(resolve_config, dict) else "best overall quality"

    if judge_name and len(branches) > 1:
        numbered = "\n\n".join(
            f"--- Branch {i+1} ---\n{b}" for i, b in enumerate(branches)
        )
        judge_prompt = (
            f"You are judging {len(branches)} responses. "
            f"Criteria: {criteria}\n\n{numbered}\n\n"
            f"Select the best branch by number and explain why. "
            f"Then reproduce the winning branch's content in full."
        )
        ctx.state.add_message({"role": "user", "content": judge_prompt})
        await _execute_step({"step": judge_name}, ctx)
    elif branches:
        ctx.state.add_message({"role": "assistant", "content": branches[0]})

    return None


# ------------------------------------------------------------------
# ralph — task-list progression loop
# ------------------------------------------------------------------


async def _execute_ralph(
    node: dict,
    ctx: _ExecutionContext,
    path: list,
    resume_from: list | None = None,
) -> str | None:
    max_tasks = node.get("max", 10)
    steps = node.get("steps", node.get("work", []))
    done_pattern = node.get("done", "DONE")

    start_task = 0
    if resume_from and len(resume_from) > len(path):
        start_task = resume_from[len(path)]

    for task_num in range(start_task, max_tasks):
        ctx.stream.loop_iteration(task_num + 1, max_tasks)

        task_path = path + [task_num]
        ctx.state.flow_position = task_path

        inner_resume = resume_from if (resume_from and task_num == start_task) else None
        result = await _execute(steps, ctx, task_path, inner_resume)
        if result == "end":
            return None

        last_content = _last_assistant_content(ctx.state)
        if done_pattern in last_content:
            ctx.stream.route(done_pattern, "all_done")
            return None
        ctx.stream.route("NEXT", "continue")

    return None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _last_assistant_content(state: State) -> str:
    for msg in reversed(state.messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            return msg["content"]
    return ""


def _summarize_tool_calls(tool_calls: list[dict]) -> list[str]:
    queries = []
    for tc in tool_calls:
        fn = tc.get("function", {})
        name = fn.get("name", "unknown")
        try:
            args = json.loads(fn.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            args = {}
        query = args.get("query") or args.get("input") or name
        if len(str(query)) > 80:
            query = str(query)[:80] + "..."
        queries.append(str(query))
    return queries


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think_streaming(text: str) -> str:
    return _THINK_RE.sub("", text)


def _resolve_count(count_value, params: dict) -> int:
    if isinstance(count_value, int):
        return count_value
    if isinstance(count_value, str) and count_value.startswith("{") and count_value.endswith("}"):
        param_name = count_value[1:-1]
        return int(params.get(param_name, 1))
    return int(count_value)


def _stable_counter_name(prefix: str, node: dict) -> str:
    """Generate a stable counter name from a flow node's structure."""
    digest = md5(json.dumps(node, sort_keys=True, default=str).encode()).hexdigest()[:8]
    return f"{prefix}_{digest}"
