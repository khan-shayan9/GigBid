# ADR 0003: GigSim tunables as data, SQLite state

Status: accepted (Phase 2)

## Context
`gigsim/` is frozen at tag `gigsim-v1` after Phase 2, but grader data, the policy update and
tuning of the client simulation all arrive later. GigSim must not import from `agent/`. Its
public host sleeps and restarts.

## Decision
- Every tunable lives outside `gigsim/`: `data/gigsim_seed/sim_config.json`,
  `data/policy_pack/<version>.yaml`, and env variables (tokens, paths, epoch, LLM endpoint).
- The prompt for the optional LLM client simulation is a data file,
  `data/gigsim_seed/client_sim_prompt.md`. This is a deliberate exception to "every prompt
  lives in `agent/prompts/`": it is the simulator's prompt, not an agent's, and keeping it out of
  `agent/` keeps hidden client behaviour away from the agent.
- State that must survive a restart (proposals, events, messages, Connects ledger, idempotency
  keys, clock offset and epoch) is kept in SQLite through the standard library; no new
  dependency.

## Consequences
- New grader jobs and clients and policy v2 are data changes (tests prove the v2 switch).
- One process owns the SQLite file, so GigSim runs a single uvicorn worker.
- The policy schema can express content patterns, required phrases, length limits, Connects
  cost rules (add or set) and a daily submission cap; anything beyond that needs a new GigSim
  version.
