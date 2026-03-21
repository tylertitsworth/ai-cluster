import os

from fastapi import FastAPI
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from ray import serve

from graph import TOOLS, AgentActor, ToolActor, build_graph

OLLAMA_BASE_URL = os.environ.get(
    "OLLAMA_BASE_URL", "http://ollama.ollama.svc.cluster.local:11434"
)
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "nemotron-3-nano-30b-full")

SUMMARIZER_PROMPT = (
    "You are a summarizer. Read the user's message and distill it into a clear, "
    "concise task description for another agent to act on. Do not perform the task "
    "yourself — just restate what needs to be done."
)

EXECUTOR_PROMPT = (
    "You are an executor. Carry out the task described in the conversation using "
    "your available tools (current time and math). Respond with the final answer."
)

fastapi_app = FastAPI(title="LangGraph Agent")


class InvokeRequest(BaseModel):
    query: str


class InvokeResponse(BaseModel):
    response: str


@serve.deployment
@serve.ingress(fastapi_app)
class LangGraphService:
    def __init__(self):
        summarizer = AgentActor.remote(
            OLLAMA_BASE_URL, OLLAMA_MODEL, SUMMARIZER_PROMPT,
        )
        executor = AgentActor.remote(
            OLLAMA_BASE_URL, OLLAMA_MODEL, EXECUTOR_PROMPT, tools=TOOLS,
        )
        tool_actor = ToolActor.remote(TOOLS)
        self.graph = build_graph(summarizer, executor, tool_actor)

    @fastapi_app.get("/health")
    def health(self):
        return {"status": "ok"}

    @fastapi_app.post("/invoke")
    async def invoke(self, request: InvokeRequest) -> InvokeResponse:
        result = await self.graph.ainvoke(
            {"messages": [HumanMessage(content=request.query)]}
        )
        return InvokeResponse(response=result["messages"][-1].content)


app = LangGraphService.bind()
