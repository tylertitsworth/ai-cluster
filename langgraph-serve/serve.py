import json
import logging
import os
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel
from ray import serve

from workflows import WORKFLOWS

logger = logging.getLogger("LangGraphService")

OLLAMA_BASE_URL = os.environ.get(
    "OLLAMA_BASE_URL", "http://ollama.ollama.svc.cluster.local:11434"
)
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "nemotron-3-nano-30b-full")
CHECKPOINT_DB = os.environ.get("CHECKPOINT_DB", "/data/checkpoints.db")

fastapi_app = FastAPI(title="LangGraph Agent")


class InvokeRequest(BaseModel):
    workflow: str = "example"
    query: str
    thread_id: str | None = None


class InvokeResponse(BaseModel):
    workflow: str
    thread_id: str
    response: str


def _resolve(workflow_name: str):
    entry = WORKFLOWS.get(workflow_name)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown workflow '{workflow_name}'. "
                   f"Available: {list(WORKFLOWS.keys())}",
        )
    return entry


@serve.deployment
@serve.ingress(fastapi_app)
class LangGraphService:
    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.base_url = OLLAMA_BASE_URL
        self.model = OLLAMA_MODEL
        conn = aiosqlite.connect(CHECKPOINT_DB)
        self.checkpointer = AsyncSqliteSaver(conn)

    @fastapi_app.get("/health")
    def health(self):
        return {"status": "ok"}

    @fastapi_app.get("/workflows")
    def list_workflows(self):
        return {"workflows": list(WORKFLOWS.keys())}

    @fastapi_app.post("/invoke")
    async def invoke(self, request: InvokeRequest) -> InvokeResponse:
        entry = _resolve(request.workflow)
        thread_id = request.thread_id or str(uuid.uuid4())
        logger.info(">>> workflow=%s thread=%s query=%s", request.workflow, thread_id, request.query)
        response = await entry["run"](
            self.base_url, self.model, request.query, thread_id, self.checkpointer,
        )
        logger.info("<<< workflow=%s thread=%s response=%s", request.workflow, thread_id, response)
        return InvokeResponse(workflow=request.workflow, thread_id=thread_id, response=response)

    @fastapi_app.post("/stream")
    async def stream(self, request: InvokeRequest):
        entry = _resolve(request.workflow)
        thread_id = request.thread_id or str(uuid.uuid4())
        logger.info(">>> stream workflow=%s thread=%s query=%s", request.workflow, thread_id, request.query)

        async def event_generator():
            async for chunk in entry["stream"](
                self.base_url, self.model, request.query, thread_id, self.checkpointer,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")


app = LangGraphService.bind()
