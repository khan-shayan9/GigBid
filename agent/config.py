"""Load agent/config.yaml and the node prompts in agent/prompts/."""

from functools import cache
from pathlib import Path

import yaml

AGENT_DIR = Path(__file__).resolve().parent


@cache
def load_config() -> dict:
    return yaml.safe_load((AGENT_DIR / "config.yaml").read_text(encoding="utf-8"))


def load_prompt(node: str) -> str:
    """The prompt text of agent/prompts/<node>.md, without its front matter."""
    text = (AGENT_DIR / "prompts" / f"{node}.md").read_text(encoding="utf-8")
    if text.startswith("---\n"):
        text = text.split("\n---\n", 1)[1]
    return text.lstrip()


def load_policy(version: str | None = None) -> dict:
    """The active marketplace policy (data/policy_pack/<version>.yaml): data, not code."""
    version = version or load_config()["policy"]["version"]
    path = AGENT_DIR.parent / "data" / "policy_pack" / f"{version}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))
