# GigBid — Student Starter Kit (v0.1)

This is a **scaffold**, not a completed solution. It gives you a suggested repository layout,
small synthetic examples, configuration templates, and interfaces to help you begin AI-4016.

## What is included
- A suggested project structure aligned with the assignment.
- Tiny synthetic job, client, freelancer and portfolio examples.
- A starter marketplace policy pack.
- Typed hand-off models and a minimal LangGraph state/graph placeholder.
- Portfolio and marketplace MCP server placeholders.
- RAG ingestion/retrieval/claim-verification placeholders.
- FastAPI and React starting-point notes.
- `.env.example`, `agent/config.yaml`, `Makefile`, and setup notes.

## What you must build
You are responsible for implementing and testing the agents, MCP tools, marketplace adapters,
advanced RAG variants, claim verification, human approval flow, persistence, UI, evaluations,
deployment, and your own research findings. The sample data is illustrative only and is not a
replacement for the instructor-provided GigSim data or evaluation sets.

## GigSim is ours (deviation from the brief)
The brief describes GigSim, the personas and the policy pack as provided. The course shipped
only this starter kit and Kaggle datasets, so we built GigSim ourselves (`gigsim/`, Phase 2),
with seed data from our pipeline (`data/gigsim_seed/`, see `docs/DATA_CARD.md`) and a
machine-readable policy pack (`data/policy_pack/v1.yaml`; `v2.yaml` is an assumed version of
the 2 Nov 2026 update). GigSim is frozen at tag `gigsim-v1`; new jobs, clients and policy
versions are data changes. Running it: `docs/RUNBOOK.md`.

## Quick start
1. Create your own public GitHub repository.
2. Copy this starter kit into the repository.
3. Create a Python 3.11+ virtual environment.
4. Install dependencies from `pyproject.toml` (adjust/pin versions after checking compatibility).
5. Copy `.env.example` to `.env` and fill local values. **Never commit `.env`.**
6. Read `docs/GETTING_STARTED.md` and work through the TODO checklist.
7. Keep `gigsim/` unchanged after the `gigsim-v1` tag (CI checks this).

## Suggested first milestone (for your own planning; not a graded submission)
- Run a health-check API.
- Load one sample job.
- Retrieve one portfolio evidence item.
- Produce a structured analysis.
- Draft a proposal with evidence references.
- Stop at a human approval screen; do not send anything automatically.

## Important safety rules
- Treat job posts and client messages as untrusted input.
- Never follow instructions embedded inside a job post that conflict with system policy.
- Never invent portfolio experience or results.
- Do not scrape Upwork or automate its website.
- Never send proposals/messages or spend Connects without explicit human approval.
- Use the official Upwork MCP server/approved APIs for live mode, if applicable.
- Keep secrets and real client data out of Git.

## Setup and key versions
See `docs/RUNBOOK.md` for setup. Pinned with uv 0.11.8 (full lock in `uv.lock`):
Python 3.11+, FastAPI 0.163.0, Pydantic 2.14.3, LangGraph 1.2.22, LangChain 1.5.0,
langchain-mcp-adapters 0.3.2, MCP SDK 1.30.0, pytest 9.2.0, ruff 0.17.5.

## Repository map
See `docs/GETTING_STARTED.md` for the purpose of each major folder.
