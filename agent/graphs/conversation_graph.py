"""The conversation graph (C1): one thread per client conversation. Wiring only.

START -> classify_intent
  scam_signal       -> END (nothing is drafted; the UI shows the flag)
  interview_request -> offer_slots -> draft_reply
  otherwise         -> draft_reply
draft_reply -> check_reply (blocked -> END) -> approve_reply (interrupt)
  approved -> send_reply -> END; rejected -> END
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from agent.nodes.client_liaison import (
    approve_reply,
    check_reply,
    classify_intent,
    draft_reply,
    offer_slots,
    send_reply,
)
from agent.state import ConversationState


def _after_intent(state: ConversationState) -> str:
    return {"scam_signal": END, "interview_request": "offer_slots"}.get(
        state["intent"], "draft_reply")


def _after_check(state: ConversationState) -> str:
    return "approve_reply" if state["compliance_verdict"]["allowed"] else END


def _after_approval(state: ConversationState) -> str:
    status = state.get("approval_status")
    if status == "blocked_after_edit":  # back to the user with the reason, to fix and approve
        return "approve_reply"
    return "send_reply" if status == "approved" else END


def build_conversation_graph(checkpointer: Any = None) -> Any:
    graph = StateGraph(ConversationState)
    for name, node in [("classify_intent", classify_intent), ("offer_slots", offer_slots),
                       ("draft_reply", draft_reply), ("check_reply", check_reply),
                       ("approve_reply", approve_reply), ("send_reply", send_reply)]:
        graph.add_node(name, node)
    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges("classify_intent", _after_intent,
                                [END, "offer_slots", "draft_reply"])
    graph.add_edge("offer_slots", "draft_reply")
    graph.add_edge("draft_reply", "check_reply")
    graph.add_conditional_edges("check_reply", _after_check, ["approve_reply", END])
    graph.add_conditional_edges("approve_reply", _after_approval,
                                ["approve_reply", "send_reply", END])
    graph.add_edge("send_reply", END)
    return graph.compile(checkpointer=checkpointer)
