"""Chat models per node, from the active profile in agent/config.yaml (never named in code)."""

import os

from langchain_openai import ChatOpenAI

from agent.config import load_config


def chat_model(node: str, config: dict | None = None, **overrides: object) -> ChatOpenAI:
    """The node's model on its profile's provider (Groq and OpenRouter are OpenAI-compatible).

    `overrides` (e.g. `model`, `max_retries`) are for evaluation runs only.
    """
    config = config or load_config()
    models = config["models"]
    profile = models["profiles"][os.environ.get("MODEL_PROFILE") or models["profile"]]
    providers = config["llm_providers"]
    provider = providers[profile["provider"]]
    settings = {"model": profile["nodes"][node], "base_url": provider["base_url"],
                "api_key": os.environ[provider["api_key_env"]],
                "timeout": providers["timeout_s"], "max_retries": providers["max_retries"]}
    return ChatOpenAI(**settings | overrides)
