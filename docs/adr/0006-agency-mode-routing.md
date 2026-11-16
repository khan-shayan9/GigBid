# ADR 0006: Agency mode (X1) routes a job before the bid graph

Status: accepted (Phase 8)

## Context
- The signature extension is X1, agency mode: a team of freelancers, and GigBid routes each job
  to the best-fit member. The "draft in that member's voice" half was dropped by the user (it
  needs many LLM drafts under the Groq daily cap). Drafts are grounded in the routed member's
  portfolio only.
- Each member is a persona: its own GigSim user and its own portfolio. `apps/api` opens one MCP
  connection per persona (`Runtime.open_mcp(persona, servers)`), and the bid graph runs on one
  connection. So the graph cannot compare members from inside one run.
- Approve, retry, the pipeline board, messages and analytics took the persona from the account's
  profile, so a thread bidding as another member would resume on the wrong connection.

## Decision
- **Routing runs before the graph, in the run's first segment.** A bid thread started with
  agency on carries `agency` in its input. At the start of its first segment (the worker, or an
  API task; never the HTTP request), `apps/api/services/agency.py` runs the shipped Fit Matcher
  node on each member's Portfolio server in parallel, and `agent/nodes/router.py` `route()`
  picks the member and returns a `RouteDecision` hand-off. The segment then opens its MCP
  connection as that member, and the bid graph runs unchanged. The eval runner calls the same
  `fit_for` and `route`. A member whose Portfolio server is unavailable is left out; if none
  answers, the thread runs as the account's persona.
- **The router only picks a member.** The decision node is still the only place that decides
  bid or skip. The router uses fit reports only: higher fit score, then higher mean best evidence
  score, then the order of `api.personas`. Nothing from `data/pipeline/` is used.
- **The thread owns its member.** The graph input carries `member` (and the `route`), kept in
  `GigBidState` / `ConversationState`. Resume and retry read the member from the checkpoint. With
  agency on, the board, messages and analytics read every member's marketplace proposals and
  messages, and match a proposal to a thread by (member, job). Members a thread was routed to
  are remembered per account, so turning agency off later does not hide their proposals,
  replies or outcomes. One job still has one thread per account (`<account>:bid:<job>`), so two members
  never bid on the same job.
- **Off by default.** `Profile.agency` is `false`; with it off, every path behaves as accepted in
  Phase 7 (the member is the account's persona).

## Consequences
- Agency mode runs the Fit Matcher once per member before the graph runs it again for the chosen
  member: no LLM calls, but one Portfolio MCP connection per member, and a stdio server takes
  seconds to start. That is why routing runs in the background segment, opening the members in
  parallel. Routing time is not measured by a committed runner yet.
- Routing accuracy can only be checked against how `data/pipeline/` assigned dev jobs to
  personas; no dev job is labelled bid for two personas (`evals/results/agency_routing_dev.json`).
- The Connects balance shown in settings is still the account's own persona's.
