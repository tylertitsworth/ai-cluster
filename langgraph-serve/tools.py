"""Tool definitions. Add new @tool functions here and append to TOOLS."""

from datetime import datetime, timezone

from langchain_core.tools import tool


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
