"""V1: split a job post into its requirements, one retrieval each (merged by the retriever).

The model call and the prompt are passed in, so `rag/` names no model and holds no prompt.
"""

import re
from collections.abc import Callable

MAX_REQUIREMENTS = 8
LIST_MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")
THINKING = re.compile(r"<think>.*?</think>", re.DOTALL)  # Qwen3 may return its reasoning inline

Complete = Callable[[str], str]  # prompt in, model reply out


def decompose(post: str, complete: Complete, prompt: str) -> list[str]:
    """The post's requirements, one per line of the model's reply; the whole post if none."""
    reply = visible(complete(prompt.format(job_post=post)))
    lines = [LIST_MARKER.sub("", line).strip() for line in reply.splitlines()]
    return [line for line in lines if line][:MAX_REQUIREMENTS] or [post]


def visible(reply: str) -> str:
    """The reply without any inline <think> reasoning block."""
    return THINKING.sub("", reply).strip()
