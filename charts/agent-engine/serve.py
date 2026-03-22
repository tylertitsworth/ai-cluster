import asyncio
import logging
import os
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from ray import serve

from engine.operators import apply_operators
from engine.registry import WorkflowRegistry
from engine.state import CheckpointStore
from engine.stream import StreamWriter

logger = logging.getLogger("AgentEngine")

CHECKPOINT_DB = os.environ.get("CHECKPOINT_DB", "/data/checkpoints.db")

fastapi_app = FastAPI(title="Agent Engine")


class RunRequest(BaseModel):
    workflow: str
    query: str
    thread_id: str | None = None
    params: dict = {}
    agent_overrides: dict = {}
    operators: list = []


class RunResponse(BaseModel):
    workflow: str
    thread_id: str
    response: str


class ResumeRequest(BaseModel):
    thread_id: str


@serve.deployment
@serve.ingress(fastapi_app)
class AgentEngine:
    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.registry = WorkflowRegistry()
        self.checkpoints = CheckpointStore(CHECKPOINT_DB)
        asyncio.get_event_loop().create_task(self._init())

    async def _init(self):
        await self.checkpoints.init()
        asyncio.create_task(self.registry.watch())

    @fastapi_app.get("/health")
    def health(self):
        return {"status": "ok"}

    @fastapi_app.get("/workflows")
    def list_workflows(self):
        return {"workflows": self.registry.list_workflows()}

    @fastapi_app.get("/workflows/{name}")
    def get_workflow(self, name: str):
        config = self.registry.get(name)
        if not config:
            raise HTTPException(404, f"Unknown workflow: {name}")
        return {
            "name": config["name"],
            "description": config.get("description", ""),
            "tier": config.get("tier", "default"),
            "params": config.get("params", {}),
            "agents": {
                k: {"provider": v.get("provider"), "tools": v.get("tools", [])}
                for k, v in config.get("agents", {}).items()
            },
            "flow": config.get("flow"),
        }

    @fastapi_app.post("/run")
    async def run(self, request: RunRequest) -> RunResponse:
        """Invoke a workflow and return the final result."""
        config = self.registry.get(request.workflow)
        if not config:
            raise HTTPException(404, f"Unknown workflow: {request.workflow}")

        config = apply_operators(config, request.operators)

        params, errors = self.registry.validate_params(request.workflow, request.params)
        if errors:
            raise HTTPException(400, f"Invalid params: {errors}")

        thread_id = request.thread_id or str(uuid.uuid4())

        from engine.executor import run_workflow

        try:
            stream = StreamWriter()
            result = await run_workflow(
                config=config,
                query=request.query,
                thread_id=thread_id,
                params=params,
                agent_overrides=request.agent_overrides,
                stream=stream,
                checkpoints=self.checkpoints,
                registry=self.registry,
            )
        except Exception:
            logger.exception("Workflow '%s' failed", request.workflow)
            raise HTTPException(500, "Workflow failed unexpectedly")

        return RunResponse(
            workflow=request.workflow,
            thread_id=thread_id,
            response=result,
        )

    @fastapi_app.post("/stream")
    async def stream(self, request: RunRequest):
        """Invoke a workflow and stream SSE events."""
        config = self.registry.get(request.workflow)
        if not config:
            raise HTTPException(404, f"Unknown workflow: {request.workflow}")

        config = apply_operators(config, request.operators)

        params, errors = self.registry.validate_params(request.workflow, request.params)
        if errors:
            raise HTTPException(400, f"Invalid params: {errors}")

        thread_id = request.thread_id or str(uuid.uuid4())

        from engine.executor import run_workflow

        stream = StreamWriter()

        async def event_generator():
            async def _run():
                try:
                    await run_workflow(
                        config=config,
                        query=request.query,
                        thread_id=thread_id,
                        params=params,
                        agent_overrides=request.agent_overrides,
                        stream=stream,
                        checkpoints=self.checkpoints,
                        registry=self.registry,
                    )
                except Exception:
                    logger.exception("Workflow '%s' failed", request.workflow)
                    stream.error("system", "Workflow failed unexpectedly")
                finally:
                    if not stream._closed:
                        stream.close()

            task = asyncio.create_task(_run())
            async for event_str in stream.events():
                yield event_str
            await task

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
        )

    @fastapi_app.post("/resume")
    async def resume(self, request: ResumeRequest):
        """Resume a checkpointed workflow."""
        state = await self.checkpoints.load(request.thread_id)
        if not state:
            raise HTTPException(404, f"No checkpoint found for thread: {request.thread_id}")

        from engine.executor import resume_workflow

        stream = StreamWriter()

        async def event_generator():
            async def _run():
                try:
                    await resume_workflow(
                        state=state,
                        stream=stream,
                        checkpoints=self.checkpoints,
                        registry=self.registry,
                    )
                except Exception:
                    logger.exception("Resume failed for thread %s", request.thread_id)
                    stream.error("system", "Resume failed unexpectedly")
                finally:
                    if not stream._closed:
                        stream.close()

            task = asyncio.create_task(_run())
            async for event_str in stream.events():
                yield event_str
            await task

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
        )


app = AgentEngine.bind()
