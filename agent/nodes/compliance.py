"""Compliance Guard: check the draft against the active policy pack; it alone can block.

The rules are data (data/policy_pack/<version>.yaml, chosen by `policy.version` in config), so
the platform policy update is a data change.
"""

import re

from agent.config import load_policy
from agent.handoffs import ComplianceVerdict
from agent.state import GigBidState


def check(text: str, policy: dict, applies_to: str = "proposal") -> ComplianceVerdict:
    violations = [rule["message"] for rule in policy.get("forbidden", [])
                  if applies_to in rule["applies_to"] and re.search(rule["pattern"], text)]
    violations += [rule["message"] for rule in policy.get("required", [])
                   if applies_to in rule["applies_to"]
                   and not any(phrase.lower() in text.lower() for phrase in rule["any_of"])]
    if len(text) > policy.get("max_length", {}).get(applies_to, len(text)):
        violations.append(f"Longer than the {applies_to} limit.")
    return ComplianceVerdict(allowed=not violations, violations=violations)


async def compliance(state: GigBidState) -> GigBidState:
    verdict = check(state["proposal_draft"]["cover_letter"], load_policy())
    return {"compliance_verdict": verdict.model_dump()}
