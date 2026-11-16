# Signature extension: X1 agency mode

GigBid runs a team of freelancers. With agency mode on, each job goes to the team member whose
portfolio fits it best, and that member's bid thread runs as usual: their portfolio grounds the
draft, their marketplace account receives the proposal after approval, and their Connects pay
for it. The design is in ADR 0006 (`docs/adr/0006-agency-mode-routing.md`).

**Scope.** The brief's X1 also asks for drafts "in that member's voice". We dropped that half:
it needs many LLM drafts to measure, and the Phase 7 cost run measured only 3 proposals before
the Groq daily cap stopped it (`evals/results/cost_latency_dev.json` has the 3). Drafts are grounded in the routed
member's portfolio, but not styled after their past proposals.

## How it works
- The team is the three personas in `api.personas` (`agent/config.yaml`). Agency mode is the
  `agency` switch in Settings; it is off by default, so the reviewer login and the CI eval gates
  behave as they did in Phase 7.
- A bid thread started with agency on (from the inbox or the worker's scheduled scouting) is
  routed at the start of its first run segment, in the worker or an API task, never in the HTTP
  request (`apps/api/services/agency.py`). It runs the shipped Fit Matcher on each member's
  Portfolio server in parallel, and `agent/nodes/router.py` returns a `RouteDecision`: the
  member with the highest fit score; on a tie, the stronger mean evidence score; then the first
  member listed. It reads fit reports only. A member whose Portfolio server is down is left out.
- The router only picks a member. The decision node still decides bid or skip for that member,
  and every send still waits for approval.
- The thread keeps its member in its state, so approve and retry run as that member. The job
  detail page shows each member's fit and why the job was routed; the inbox shows "As <member>".
  One job has one thread per account, so two members never bid on the same job. The board,
  messages and analytics read every member's proposals and messages, and stay correct if agency
  mode is turned off later.

## Measurement
`uv run python -m evals.runners.agency_routing` writes `evals/results/agency_routing_dev.json`.
It calls the same `fit_for` and `route` functions the API calls, on dev seed data with the
shipped retrieval variant (V1), and makes no LLM calls.

| Measure (dev) | n | Accuracy |
|---|---|---|
| Router: routed member is the labelled member | 170 | 0.847 |
| Router on jobs where two or more members tie on fit | 28 | 0.714 |
| Contrast jobs: labelled bid for one member and skip for another | 11 | 0.909 |
| Best fixed-member baseline (always `fullstack_dev`) | 170 | 0.341 |
| Random baseline (expected) | — | 0.333 |

By labelled member: `fullstack_dev` 0.948 (n 58), `ai_ml_engineer` 0.804 (n 56),
`data_analyst` 0.786 (n 56).

**Does routing change bid or skip?** Barely. The same file runs the decision node (no LLM) in two
ways: one persona per account, each labelled (job, persona) pair decided as that persona; and
agency mode, each dev job decided as its routed member, gold "bid" when any persona is labelled
bid.

| Setting (dev) | n | Gold bids | Predicted bids | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| One persona per account (labelled pairs) | 565 | 170 | 150 | 0.427 | 0.376 | 0.400 |
| Agency mode (jobs, routed member) | 522 | 170 | 164 | 0.415 | 0.400 | 0.407 |

Routing gets jobs to the right member, but the bid or skip quality is set by the decision node's
thresholds and the risk signals, not by who bids. The finding is negative for "the team bids
better". What agency mode adds is reach: one account bids as whichever member fits, across all
three fields, at about the same bid quality. The first row pools all three personas' labelled
pairs; a real one-persona account would see only its own field's jobs.

## Limits
- **Circular gold.** No dev job is labelled bid for two personas, so "right member" means the
  persona `data/pipeline/` assigned the job to. The router never reads those rules, but a high
  score shows agreement with our own generator, not that another member could not do the job.
  (Job, member) pairs with no label are unknown, not skip.
- **Tuning.** The tie-break was chosen after a scratch run on dev showed 28 ties at the top; it
  was not tuned further. The held-out split was not used for routing or tuning (only its label
  counts were looked at).
- **Small contrast set.** The contrast result is 10 of 11 jobs.
- **Cost.** Routing runs the Fit Matcher once per member, then the graph runs it again for the
  chosen member: no LLM tokens, but one Portfolio MCP connection per member, which is slow to
  open with stdio servers. Routing time is not measured by a committed runner, and it was not
  run on the deployed VM. In compose the MCP servers are stdio processes, so a scout tick with
  two segments at once (`worker.max_jobs`) can start up to six Portfolio processes, each loading
  the embedder; whether the B2s VM has the memory for that is unverified.
- **Not traced.** Routing runs outside the node guard and the Langfuse trace, and analytics
  latency starts at the first checkpoint, so routing time is missing from R8's numbers.
- **More marketplace calls.** With agency on, the board, messages, analytics and the outcome
  cron open one marketplace connection per member, one after another.
- **Team gold is a lower bound.** In the decision table, pairs with no label count as not bid,
  so a job another member could do is scored against.
- **No voice.** Drafts are not styled per member (see Scope).
- The Connects balance in Settings is still the account's own persona's.
