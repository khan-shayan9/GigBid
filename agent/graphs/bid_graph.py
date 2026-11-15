"""The bid graph (C1): one thread per job. Wiring only; the logic lives in agent/nodes/.

START -> (Job Analyst | Risk Assessor | Fit Matcher, in parallel) -> decision
  skip -> END
  bid  -> pricing -> writer -> verifier -> critic
            critic fails and revisions < budgets.max_revisions -> writer (with the reasons)
          -> compliance  (blocked -> END, reason in state)
          -> approval (interrupt) -> approved -> submit -> END; rejected -> END

Every node runs through agent/graphs/guard.py: retries, dead-letter and the step and token
budgets (C4, C7); a thread that stops early has `status` and the reason in `errors`.

`config["configurable"]` carries `mcp` (agent/mcp_client.py), `model` and `thread_id`.
Compile with a checkpointer so an interrupted thread survives a restart, and with a store
so approved edits reach long-term memory through agent/memory/promotion_rules.py.
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from agent.config import load_config
from agent.graphs.guard import guarded, halts
from agent.nodes.analyst import analyst
from agent.nodes.compliance import compliance
from agent.nodes.critic import critic
from agent.nodes.decision import decision
from agent.nodes.fit_matcher import fit_matcher
from agent.nodes.pricing import pricing
from agent.nodes.risk_assessor import risk_assessor
from agent.nodes.submitter import approval, submit
from agent.nodes.verifier import verifier
from agent.nodes.writer import writer
from agent.state import GigBidState

PARALLEL = ["analyst", "risk_assessor", "fit_matcher"]


def _after_decision(state: GigBidState) -> str:
    return "pricing" if state["decision"]["decision"] == "bid" else END


def _after_critic(state: GigBidState) -> str:
    max_revisions = load_config()["budgets"]["max_revisions"]
    if state["critique"]["passed"] or state.get("revisions", 0) > max_revisions:
        return "compliance"
    return "writer"


def _after_compliance(state: GigBidState) -> str:
    return "approval" if state["compliance_verdict"]["allowed"] else END


def _after_approval(state: GigBidState) -> str:
    return "submit" if state.get("approval_status") == "approved" else END


def build_bid_graph(checkpointer: Any = None, store: Any = None) -> Any:
    graph = StateGraph(GigBidState)
    for name, node in [("analyst", analyst), ("risk_assessor", risk_assessor),
                       ("fit_matcher", fit_matcher), ("decision", decision),
                       ("pricing", pricing), ("writer", writer), ("verifier", verifier),
                       ("critic", critic), ("compliance", compliance),
                       ("approval", approval), ("submit", submit)]:
        graph.add_node(name, guarded(name, node))
    for name in PARALLEL:
        graph.add_edge(START, name)
    graph.add_edge(PARALLEL, "decision")  # waits for all three branches
    graph.add_conditional_edges("decision", halts(_after_decision), ["pricing", END])
    for source, target in [("pricing", "writer"), ("writer", "verifier"), ("verifier", "critic")]:
        graph.add_conditional_edges(source, halts(lambda _, target=target: target), [target, END])
    graph.add_conditional_edges("critic", halts(_after_critic), ["writer", "compliance", END])
    graph.add_conditional_edges("compliance", halts(_after_compliance), ["approval", END])
    graph.add_conditional_edges("approval", halts(_after_approval), ["submit", END])
    graph.add_edge("submit", END)
    return graph.compile(checkpointer=checkpointer, store=store)
