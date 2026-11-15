# R&D C: one ReAct agent vs a supervisor team vs our hand-written bid graph

All numbers below come from `evals/results/rnd_c_dev.json` (summary) and `rnd_c_dev.csv` (one row
per architecture and job). Regenerate them with
`uv run python -m evals.runners.rnd_c_architectures --jobs 7`; cached rows in
`data/processed/rnd_c/` mean the rerun costs no tokens.

## Hypothesis
A hand-written graph with typed hand-offs is cheaper, faster and safer, because write tools can
only be reached after an `interrupt()` approval. An LLM-driven ReAct agent or supervisor team
judges messy posts better, but costs tokens, takes longer and could call a write tool on its own.

## Setup
- **Task:** triage only: bid or skip, plus a scam flag, scored against the gold labels in
  `evals/datasets/dev.jsonl`. Drafting is out of scope.
- **Architectures:**
  - `react`: `langgraph.prebuilt.create_react_agent` with all tools (`agent/prompts/rnd_c_react.md`).
  - `supervisor`: `langgraph-supervisor` 0.0.31 with workers `risk_analyst`, `fit_analyst` and
    `proposal_writer` (`agent/prompts/rnd_c_supervisor.md`).
  - `graph`: `build_bid_graph()` stopped before pricing, the step right after its decision.
- **Tools:** one shared in-process backend over the GigSim seed and the persona corpora:
  `get_client_history`, `search_evidence`, `get_market_rates`, and fake `create_proposal_draft`
  and `submit_proposal`. The fake write tools record every call; a call with `dry_run` false
  counts as a write without approval.
- **Model:** both baselines run on `openai/gpt-oss-120b`, the model the `critic` node is routed
  to, with `max_tokens` 1500. gpt-oss-20b's daily Groq quota had run out.
- **Sample:** 50 dev jobs drawn by seed 4016, stratified with scams and injections over-sampled
  and then shuffled. The run was stopped at the deadline, so **n = 7 jobs**: 4 other skips,
  1 injection, 1 bid and 1 scam. The ReAct agent used about 5k tokens a job and the supervisor
  about 7k; Groq's free tier allows 200k tokens a day per model.

## Results (n = 7, dev)
| | ReAct | Supervisor | Our graph |
|---|---|---|---|
| Decision accuracy | 0.857 | 0.857 | 0.143 |
| Bid recall | 1.0 | 0.0 | 1.0 |
| Scam skipped (1 job) | 1/1 | 1/1 | 0/1 |
| Injection skipped (1 job) | 1/1 | 1/1 | 0/1 |
| Scam flags on non-scams | 0 | 2 | 0 |
| Jobs with an unapproved write | 0 | 0 | 0 (writes only after `interrupt()`) |
| Jobs with any write-tool call | 0 | 0 | 0 |
| Mean tool calls | 2.29 | 1.71 | 5.43 |
| Mean tokens per job | 5,282 | 6,800 | n/a (no model call before the decision) |
| Latency p50 / p95 (s) | 20.7 / 48.1 | 29.1 / 101.0 | n/a (see below) |

**The graph row.** The graph bid on all 7 jobs. This is real behaviour of the shipped nodes, not
a harness artefact. Checked directly:
- The Fit Matcher counts a requirement as covered whenever `search_evidence` returns any item
  (a recorded shortcut). Dense search always returns items, so the fit score is always 1.0.
- The Risk Assessor's config regexes scored the cheque scam (job-00219) at 0.0 and the injection
  post (job-00337) at 0.3. Both are under the 0.70 skip threshold.

So the graph decides on regex risk alone. Its 0 tokens and about 0.2 s per job are measured, but
they are not comparable with the baselines, because no model runs on its triage path. They are
shown as n/a above.

## Findings
- On these 7 jobs both LLM baselines judged far better than our rule-based triage. That is
  evidence that the Fit Matcher and Risk Assessor shortcuts need a model judgement.
- Neither baseline called a write tool, with or without approval. Our graph's guarantee is
  structural: `submit` is reachable only after the `approval` interrupt (C5 tests). The
  baselines' safety rests only on the prompt.
- The supervisor cost more tokens than the single ReAct agent, had the slowest tail, never bid
  (bid recall 0 on the one bid job) and flagged 2 non-scams as scams.

## Limits
- **n = 7.** One scam, one injection and one bid job. No rate here is statistically meaningful;
  the 50-job run did not fit the Groq daily quota before the deadline.
- Baseline latency includes Groq rate-limit back-off on the free tier.
- One model, one seed, one prompt per baseline. The prompts give general policy only, never the
  label rules in `data/pipeline/`.
- Triage only. Drafting cost, Critic loops and outcome rates are not compared.
