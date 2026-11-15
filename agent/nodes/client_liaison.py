"""Client Liaison: classify a client's message, offer interview slots, draft the reply, and
send it only after approval (the conversation graph's nodes).

The intent rules are config (`liaison.intents`); slots come from the Workspace MCP tool
`find_free_slots`; the reply goes out through `send_message` after an approved interrupt.
"""

import re
from datetime import UTC, datetime, timedelta

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from agent.config import load_config, load_policy, load_prompt
from agent.mcp_client import ToolUnavailable
from agent.nodes.compliance import check
from agent.state import ConversationState

NODE = "client_liaison"
SLOTS_OFFERED = 3


def classify(message: str, rules: list[dict]) -> str:
    return next((rule["id"] for rule in rules
                 if re.search(rule["pattern"], message, re.IGNORECASE)), "question")


async def classify_intent(state: ConversationState) -> ConversationState:
    return {"intent": classify(state["message"], load_config()["liaison"]["intents"])}


async def offer_slots(state: ConversationState, config: RunnableConfig) -> ConversationState:
    start = datetime.now(UTC)
    days = load_config()["liaison"]["slot_window_days"]
    try:
        result = await config["configurable"]["mcp"].call(NODE, "find_free_slots", {
            "window_start": start.isoformat(),
            "window_end": (start + timedelta(days=days)).isoformat(), "limit": SLOTS_OFFERED})
    except ToolUnavailable:  # degraded mode: reply without times, and say why in state
        return {"slots": [], "errors": ["workspace unavailable: no interview slots offered"]}
    return {"slots": result["slots"]}


async def draft_reply(state: ConversationState, config: RunnableConfig) -> ConversationState:
    slots = "\n".join(f"- {slot['start']} to {slot['end']}" for slot in state.get("slots", []))
    message = state["message"].replace("</client_message>", "")
    prompt = load_prompt(NODE).format(intent=state["intent"], message=message,
                                      slots=slots or "(none)")
    reply = await config["configurable"]["model"].ainvoke([HumanMessage(prompt)])
    return {"reply": str(reply.content).strip()}


async def check_reply(state: ConversationState) -> ConversationState:
    return {"compliance_verdict": check(state["reply"], load_policy(), "message").model_dump()}


async def approve_reply(state: ConversationState) -> ConversationState:
    answer = interrupt({"intent": state["intent"], "client_message": state["message"],
                        "reply": state["reply"], "slots": state.get("slots", [])})
    if answer.get("action") == "reject":
        return {"approval_status": "rejected"}
    if answer.get("action") == "edit":
        verdict = check(answer["reply"], load_policy(), "message")
        if not verdict.allowed:
            return {"approval_status": "blocked_after_edit",
                    "compliance_verdict": verdict.model_dump()}
        return {"approval_status": "approved", "reply": answer["reply"]}
    return {"approval_status": "approved"}


async def send_reply(state: ConversationState, config: RunnableConfig) -> ConversationState:
    options = config["configurable"]
    sent = await options["mcp"].call(NODE, "send_message", {
        "thread_id": state["thread_id"], "text": state["reply"],
        "idempotency_key": f"reply-{options['thread_id']}", "dry_run": False})
    return {"sent": sent}
