"""GigSim settings: tunables come from a data file, deployment values from env.

gigsim/ is frozen after gigsim-v1, so every value that may need tuning lives outside it.
"""

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = "data/gigsim_seed/sim_config.json"
DEFAULT_SEED_DIRS = "data/gigsim_seed"
DEFAULT_DB_PATH = "data/processed/gigsim.sqlite"
DEFAULT_POLICY_PATH = "data/policy_pack/v1.yaml"
DEFAULT_LLM_PROMPT_PATH = "data/gigsim_seed/client_sim_prompt.md"


class RateLimit(BaseModel):
    capacity: int = Field(gt=0)
    refill_per_second: float = Field(gt=0)


class UserAccount(BaseModel):
    starting_connects: int = Field(ge=0)


class SimWeights(BaseModel):
    personal_opening: float
    any_must_have: float
    most_must_haves: float
    over_budget: float
    noise_sd: float = Field(ge=0)


class SimThresholds(BaseModel):
    hired: float
    interview: float
    replied: float


class SimDelays(BaseModel):
    viewed: float = Field(ge=0)
    replied: float = Field(ge=0)
    interview: float = Field(ge=0)
    decision: float = Field(ge=0)


class SimReplies(BaseModel):
    replied: str
    interview: str
    hired: str
    scam: str


class ClientSimConfig(BaseModel):
    mode: Literal["rules", "llm"] = "rules"
    weights: SimWeights
    thresholds: SimThresholds
    delays_min: SimDelays
    generic_openings: list[str]
    replies: SimReplies


class SimConfig(BaseModel):
    random_seed: int
    time_scale: float = Field(ge=0, description="Sim minutes per real minute; 0 freezes the clock")
    fault_rate: float = Field(ge=0, lt=1)
    rate_limit: RateLimit
    users: dict[str, UserAccount]
    default_client_prefs: dict[str, Any]
    client_sim: ClientSimConfig


class Settings(BaseModel):
    config: SimConfig
    seed_dirs: list[Path]
    db_path: Path
    tokens: dict[str, str] = Field(description="token -> user id")
    admin_token: str = ""
    epoch: str | None = None
    faults_enabled: bool = True
    policy_path: Path = Path(DEFAULT_POLICY_PATH)
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    llm_prompt: str = ""


def parse_tokens(raw: str, known_users: set[str]) -> dict[str, str]:
    """Parse 'user=token,user=token' into {token: user}; unknown users are a config error."""
    tokens: dict[str, str] = {}
    for pair in filter(None, (part.strip() for part in raw.split(","))):
        user_id, _, token = pair.partition("=")
        if user_id not in known_users or not token:
            raise ValueError(f"GIGSIM_TOKENS entry for unknown user or empty token: {user_id!r}")
        if token in tokens:
            raise ValueError(f"GIGSIM_TOKENS reuses a token (second use by {user_id!r})")
        tokens[token] = user_id
    return tokens


def load_settings() -> Settings:
    config_path = Path(os.environ.get("GIGSIM_CONFIG", DEFAULT_CONFIG_PATH))
    config = SimConfig.model_validate(json.loads(config_path.read_text(encoding="utf-8")))
    seed_dirs = os.environ.get("GIGSIM_SEED_DIRS", DEFAULT_SEED_DIRS)
    prompt_path = Path(os.environ.get("GIGSIM_LLM_PROMPT", DEFAULT_LLM_PROMPT_PATH))
    return Settings(
        config=config,
        seed_dirs=[Path(part.strip()) for part in seed_dirs.split(",") if part.strip()],
        db_path=Path(os.environ.get("GIGSIM_DB_PATH", DEFAULT_DB_PATH)),
        tokens=parse_tokens(os.environ.get("GIGSIM_TOKENS", ""), set(config.users)),
        admin_token=os.environ.get("GIGSIM_ADMIN_TOKEN", ""),
        epoch=os.environ.get("GIGSIM_EPOCH") or None,
        faults_enabled=os.environ.get("GIGSIM_FAULTS", "on").lower() != "off",
        policy_path=Path(os.environ.get("GIGSIM_POLICY", DEFAULT_POLICY_PATH)),
        llm_base_url=os.environ.get("GIGSIM_LLM_BASE_URL", ""),
        llm_model=os.environ.get("GIGSIM_LLM_MODEL", ""),
        llm_api_key=os.environ.get("GIGSIM_LLM_API_KEY", ""),
        llm_prompt=prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "",
    )
