"""V8: corrective retrieval as a small LangGraph loop (Yan et al., 2024; ADR 0005).

retrieve -> grade each hit by its reranker score -> keep the strong ones; when none is strong,
rewrite the query and retrieve again (at most `max_requeries` times); when still none, refuse:
return no evidence, so the writer has nothing to claim from.

The loop is self-contained: it imports nothing from `agent/`; search and rewrite are passed in.
"""

from collections.abc import Callable
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

Hits = list[tuple[str, float]]


class CorrectiveState(TypedDict):
    query: str
    hits: Hits
    requeries: int


def _retrieve(state: CorrectiveState, config: RunnableConfig) -> dict[str, Any]:
    options = config["configurable"]
    strong = [hit for hit in options["search"](state["query"]) if hit[1] >= options["min_score"]]
    return {"hits": strong}


def _rewrite(state: CorrectiveState, config: RunnableConfig) -> dict[str, Any]:
    return {"query": config["configurable"]["rewrite"](state["query"]),
            "requeries": state["requeries"] + 1}


def _next_step(state: CorrectiveState, config: RunnableConfig) -> str:
    if state["hits"]:
        return END
    options = config["configurable"]
    can_rewrite = options["rewrite"] is not None
    return "rewrite" if can_rewrite and state["requeries"] < options["max_requeries"] else END


def _build() -> Any:
    graph = StateGraph(CorrectiveState)
    graph.add_node("retrieve", _retrieve)
    graph.add_node("rewrite", _rewrite)
    graph.add_edge(START, "retrieve")
    graph.add_conditional_edges("retrieve", _next_step, ["rewrite", END])
    graph.add_edge("rewrite", "retrieve")
    return graph.compile()


GRAPH = _build()


def corrective(query: str, search: Callable[[str], Hits], rewrite: Callable[[str], str] | None,
               min_score: float, max_requeries: int) -> Hits:
    """Strong hits for the query (possibly rewritten); an empty list means refuse."""
    final = GRAPH.invoke({"query": query, "hits": [], "requeries": 0},
                         {"configurable": {"search": search, "rewrite": rewrite,
                                           "min_score": min_score,
                                           "max_requeries": max_requeries}})
    return final["hits"]
