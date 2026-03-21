from datetime import datetime, timezone

import ray
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph


# ---------------------------------------------------------------------------
# Tools — add new @tool functions here and append to TOOLS to extend the agent
# ---------------------------------------------------------------------------

@tool
def get_current_time() -> str:
    """Get the current UTC date and time."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


@tool
def calculate(expression: str) -> str:
    """Evaluate a math expression. Supports basic arithmetic: + - * / ** % and parentheses."""
    allowed = set("0123456789+-*/.() %e")
    if not all(c in allowed for c in expression):
        return "Error: expression contains disallowed characters"
    try:
        result = eval(expression, {"__builtins__": {}})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


TOOLS = [get_current_time, calculate]


# ---------------------------------------------------------------------------
# Ray actors — reusable building blocks for graph nodes
# ---------------------------------------------------------------------------

@ray.remote
class AgentActor:
    """Generic LLM agent. Configure its role via system_prompt and optional tools."""

    def __init__(self, base_url: str, model: str, system_prompt: str, tools: list | None = None):
        from langchain_ollama import ChatOllama

        llm = ChatOllama(base_url=base_url, model=model)
        self.llm = llm.bind_tools(tools) if tools else llm
        self.system_prompt = system_prompt

    def call(self, messages: list):
        return self.llm.invoke(
            [SystemMessage(content=self.system_prompt)] + messages
        )


@ray.remote
class ToolActor:
    """Executes tool calls requested by an agent."""

    def __init__(self, tools: list):
        self.tools_by_name = {t.name: t for t in tools}

    def call(self, tool_calls: list) -> list:
        results = []
        for tc in tool_calls:
            fn = self.tools_by_name.get(tc["name"])
            if fn is None:
                results.append(
                    ToolMessage(
                        content=f"Error: unknown tool '{tc['name']}'",
                        tool_call_id=tc["id"],
                    )
                )
                continue
            output = fn.invoke(tc["args"])
            results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
        return results


# ---------------------------------------------------------------------------
# Graph — two-agent workflow: summarizer -> executor (with tools)
#
#   START → summarizer → executor ←→ tools
#                            ↓
#                           END
# ---------------------------------------------------------------------------

def build_graph(
    summarizer: AgentActor,
    executor: AgentActor,
    tool_actor: ToolActor,
):
    """Build and compile a multi-agent graph backed by Ray actors."""

    async def summarize(state: MessagesState):
        response = await summarizer.call.remote(state["messages"])
        return {"messages": [response]}

    async def execute(state: MessagesState):
        response = await executor.call.remote(state["messages"])
        return {"messages": [response]}

    async def tools(state: MessagesState):
        results = await tool_actor.call.remote(state["messages"][-1].tool_calls)
        return {"messages": results}

    def should_continue(state: MessagesState):
        if state["messages"][-1].tool_calls:
            return "tools"
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("summarizer", summarize)
    graph.add_node("executor", execute)
    graph.add_node("tools", tools)

    graph.add_edge(START, "summarizer")
    graph.add_edge("summarizer", "executor")
    graph.add_conditional_edges("executor", should_continue, ["tools", END])
    graph.add_edge("tools", "executor")

    return graph.compile()
