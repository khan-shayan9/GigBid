"""CI rule: every prompt lives in agent/prompts/ (one .md per node), never inline in code."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE_DIRS = ("agent", "rag", "apps/api", "worker", "mcp_servers", "evals/runners")
INLINE_PROMPT = re.compile(r"""["'](You are (a|an|the) |System prompt:)""")


def test_no_prompt_text_outside_agent_prompts() -> None:
    found = [f"{path.relative_to(ROOT)}:{number}"
             for folder in CODE_DIRS for path in (ROOT / folder).rglob("*.py")
             for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
             if INLINE_PROMPT.search(line)]
    assert not found, f"inline prompt text; move it to agent/prompts/: {found}"
