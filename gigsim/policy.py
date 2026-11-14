"""Platform policy loaded from data/policy_pack/<version>.yaml: Connects costs and content rules."""

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from gigsim.models import Job

Kind = Literal["proposal", "message"]


class CostRule(BaseModel):
    id: str
    min_budget_usd: float | None = None
    min_hourly_max_usd: float | None = None
    add: int = 0
    set_to: int | None = Field(None, ge=0, description="Replace the cost instead of adding")


class PatternRule(BaseModel):
    id: str
    pattern: str
    applies_to: list[Kind]
    message: str

    @field_validator("pattern")
    @classmethod
    def _compiles(cls, pattern: str) -> str:
        re.compile(pattern)  # a bad pattern fails at startup, not on every write
        return pattern


class RequiredRule(BaseModel):
    id: str
    any_of: list[str] = Field(min_length=1)
    applies_to: list[Kind]
    message: str


class Violation(BaseModel):
    rule_id: str
    message: str


class Policy(BaseModel):
    version: str
    assumed: bool = False
    default_connects_cost: int = Field(ge=0)
    cost_rules: list[CostRule] = []
    max_length: dict[Kind, int] = {}
    forbidden: list[PatternRule] = []
    required: list[RequiredRule] = []
    submits_per_sim_day: int | None = Field(None, ge=1)

    def connects_cost(self, job: Job) -> int:
        cost = job.connects_cost if job.connects_cost is not None else self.default_connects_cost
        hourly_max = job.hourly_usd.max if job.hourly_usd else None
        for rule in self.cost_rules:
            budget_hit = rule.min_budget_usd is not None and (
                (job.budget_usd or 0) >= rule.min_budget_usd
            )
            rate_hit = rule.min_hourly_max_usd is not None and (
                (hourly_max or 0) >= rule.min_hourly_max_usd
            )
            always = rule.min_budget_usd is None and rule.min_hourly_max_usd is None
            if always or budget_hit or rate_hit:
                cost = rule.set_to if rule.set_to is not None else cost + rule.add
        return cost

    def violations(self, text: str, kind: Kind) -> list[Violation]:
        found = []
        limit = self.max_length.get(kind)
        if limit is not None and len(text) > limit:
            found.append(Violation(rule_id="max_length", message=f"Longer than {limit} characters."))
        for rule in self.forbidden:
            if kind in rule.applies_to and re.search(rule.pattern, text):
                found.append(Violation(rule_id=rule.id, message=rule.message))
        lowered = text.lower()
        for rule in self.required:
            if kind in rule.applies_to and not any(p.lower() in lowered for p in rule.any_of):
                found.append(Violation(rule_id=rule.id, message=rule.message))
        return found


def load_policy(path: Path) -> Policy:
    return Policy.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
