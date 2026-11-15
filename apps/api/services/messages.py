"""Messages service: client threads, and drafting a reply to a client's message."""

from collections import defaultdict

from apps.api.errors import ApiError
from apps.api.runtime import Runtime
from apps.api.schemas.app import MessageThread, MessageThreads
from apps.api.schemas.runs import RunRef
from apps.api.services import profiles, runs

MESSAGE_LIMIT = 500


async def _messages(rt: Runtime, persona: str) -> list[dict]:
    async with rt.open_mcp(persona, ["marketplace"]) as mcp:
        return (await mcp.call("web", "list_messages", {"limit": MESSAGE_LIMIT}))["messages"]


async def threads(rt: Runtime, account: str) -> MessageThreads:
    persona = await profiles.persona_of(rt, account)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for message in await _messages(rt, persona):
        grouped[message["thread_id"]].append(message)
    replies = {run.subject: run for run in await runs.summaries(rt, account, "conversation")}
    found = []
    for thread_id, messages in grouped.items():
        latest = next((m for m in reversed(messages) if m["sender"] == "client"), None)
        latest_id = latest["message_id"] if latest else None
        found.append(MessageThread(thread_id=thread_id, job_id=messages[0]["job_id"],
                                   messages=messages, latest_client_message_id=latest_id,
                                   reply_run=replies.get(latest_id or "")))
    found.sort(key=lambda thread: thread.messages[-1].sent_at, reverse=True)
    return MessageThreads(threads=found)


async def draft_reply(rt: Runtime, account: str, message_id: str) -> RunRef:
    persona = await profiles.persona_of(rt, account)
    message = next((m for m in await _messages(rt, persona)
                    if m["message_id"] == message_id and m["sender"] == "client"), None)
    if message is None:
        raise ApiError(404, "not_found", "No such client message.")
    return await runs.start(rt, account, persona, "conversation", message_id,
                            {"thread_id": message["thread_id"], "message": message["text"]})
