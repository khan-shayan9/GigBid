# GigBid (AI-4016 Assignment II)

Multi-agent freelancer copilot: LangGraph agents, MCP servers, advanced RAG, a FastAPI and Next.js web app, and our own GigSim marketplace simulator.

These three docs are the source of truth. Read them before any work and follow them:

@1.PROJECT_SPECIFICATION.md
@2.ARCHITECTURE.md
@3.AI_RULES.md

## Current phase

**Phase 1: Data** (see `1.PROJECT_SPECIFICATION.md` §8). Phase 0 (Scaffold) was accepted on 2026-11-15. Work on nothing beyond this phase until the user accepts it.

## Quick reminders

- The assignment brief is `../Assignment-II.pdf`. Never edit, rename or delete it.
- Raw Kaggle CSVs live in `data/raw/kaggle/` (368 MB). Never modify them. They are git-ignored (`data/raw/` in `.gitignore`).
- Never send, submit or spend Connects without an approved `interrupt()`.
- Never invent numbers. Cite `evals/results/`.
- Propose a commit at the end of each phase. Never add AI attribution to commits.
- After every major milestone (end of a phase or a large slice of one), report the work to the
  advisor model (Fable) and have it check the work before reporting to the user or proposing a
  commit. Fix what it finds; re-check large fixes with it.
