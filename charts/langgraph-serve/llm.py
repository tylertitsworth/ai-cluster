"""LLM provider factory. Creates the right LangChain chat model based on config.

Supports:
  - Ollama (default): base_url points to Ollama API (contains "ollama" or port 11434)
  - OpenAI-compatible: any other base_url (e.g. Tailscale Aperture, vLLM, etc.)
"""

import os


OLLAMA_BASE_URL = os.environ.get(
    "OLLAMA_BASE_URL", "http://ollama.ollama.svc.cluster.local:11434"
)
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "nemotron-3-nano-30b-full")

OPENAI_BASE_URL = os.environ.get(
    "OPENAI_BASE_URL", "https://ai.tail79a5c8.ts.net/v1"
)
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.3-codex")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "not-needed")


def create_llm(provider: str = "ollama", model: str | None = None):
    """Create a LangChain chat model.

    Args:
        provider: "ollama" or "openai"
        model: Model name override. If None, uses the env var default for the provider.
    """
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            base_url=OPENAI_BASE_URL,
            model=model or OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
        )
    else:
        from langchain_ollama import ChatOllama

        return ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=model or OLLAMA_MODEL,
        )
