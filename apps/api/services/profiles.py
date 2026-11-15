"""Profile service: onboarding answers, settings, connected accounts and portfolio uploads.

Profiles live in the LangGraph store under ("profile",), apart from learned memory, which only
agent/memory/promotion_rules.py writes.
"""

import os

from agent.config import load_config
from agent.mcp_client import ToolUnavailable
from apps.api.auth.token_store import has_tokens
from apps.api.errors import ApiError
from apps.api.runtime import Runtime
from apps.api.schemas.app import Connections, Profile, ProfileIn, UploadOut
from mcp_servers.marketplace.adapters.upwork_live import TOKEN_DIR
from rag.ingest.uploads import UploadRejected, save_upload

PROFILE = ("profile",)


async def get_profile(rt: Runtime, account: str) -> Profile:
    item = await rt.store.aget(PROFILE, account)
    return Profile(account=account, **(item.value if item else {}))


async def save_profile(rt: Runtime, account: str, answers: ProfileIn) -> Profile:
    if answers.persona is not None and answers.persona not in load_config()["api"]["personas"]:
        raise ApiError(422, "unknown_persona", "Choose one of the listed personas.")
    searches = [search.strip()[:200] for search in answers.saved_searches if search.strip()]
    profile = Profile(account=account, **answers.model_dump() | {"saved_searches": searches})
    await rt.store.aput(PROFILE, account, profile.model_dump(exclude={"account"}))
    return profile


async def persona_of(rt: Runtime, account: str) -> str:
    persona = (await get_profile(rt, account)).persona
    if persona is None:
        raise ApiError(409, "onboarding_required", "Choose a persona in onboarding first.")
    return persona


def marketplace_mode() -> str:
    return os.environ.get("MARKETPLACE_MODE") or load_config()["marketplace"]["mode"]


async def connections(rt: Runtime, account: str) -> Connections:
    persona = await persona_of(rt, account)
    balance = None
    try:
        async with rt.open_mcp(persona, ["marketplace"]) as mcp:
            balance = (await mcp.call("web", "get_connects_balance", {}))["balance"]
    except ToolUnavailable:
        pass
    return Connections(marketplace_mode=marketplace_mode(), marketplace=balance is not None,
                       connects_balance=balance,
                       upwork_connected=has_tokens(persona, TOKEN_DIR))


async def upload(rt: Runtime, account: str, filename: str, content: bytes) -> UploadOut:
    settings = load_config()["api"]
    try:
        saved = save_upload(account, filename, content, settings["upload_max_bytes"],
                            settings["upload_suffixes"])
    except UploadRejected as error:
        raise ApiError(422, error.code, str(error)) from error
    return UploadOut(saved_as=saved, bytes=len(content))
