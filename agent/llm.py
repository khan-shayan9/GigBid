"""Chat models per node, from the active profile in agent/config.yaml (never named in code)."""

import os

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from agent.config import load_config


def chat_model(node: str, config: dict | None = None, **overrides: object) -> Runnable:
    """The node's model on its profile's provider (Groq and OpenRouter are OpenAI-compatible).

    The client retries with backoff (`max_retries`); cheap nodes listed under the profile's
    `fallbacks` then switch model (C7). `overrides` (e.g. `model`) are for evaluation runs only
    and get no fallback, so measurements stay on the model asked for.
    """
    config = config or load_config()
    models = config["models"]
    profile = models["profiles"][os.environ.get("MODEL_PROFILE") or models["profile"]]
    providers = config["llm_providers"]
    provider = providers[profile["provider"]]
    settings = {"model": profile["nodes"][node], "base_url": provider["base_url"],
                "api_key": os.environ[provider["api_key_env"]],
                "timeout": providers["timeout_s"], "max_retries": providers["max_retries"],
                "max_tokens": providers["max_tokens"]}
    model = ChatOpenAI(**settings | overrides)
    fallback = profile.get("fallbacks", {}).get(node)
    if overrides or not fallback:
        return model
    return with_fallback(model, ChatOpenAI(**settings | {"model": fallback}))


def with_fallback(primary: BaseChatModel, fallback: BaseChatModel) -> Runnable:
    return primary.with_fallbacks([fallback])
