# ADR 0002: Self-hosted Langfuse for tracing, Phoenix as fallback

Status: accepted (Phase 0)

## Context
R8 and E3 need every run traced with one trace id end to end, plus tokens and cost per node.
Everything runs on one VPS, and self-hosted Langfuse brings its own services, so it may not fit in
the VPS memory alongside Postgres, Redis and the app.

## Decision
Use self-hosted Langfuse. If the VPS cannot hold it, switch to Arize Phoenix, which runs as a
single container. Only one tracing tool runs at a time (`3.AI_RULES.md` §2).

## Consequences
- Langfuse is added to compose in Phase 7, when tracing is built; Phase 0 does not run it.
- Tracing calls stay behind one helper so the fallback swap does not touch node code.
- The choice is revisited in Phase 7 against the measured VPS memory.
