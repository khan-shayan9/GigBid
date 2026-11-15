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
| Decision accuracy | 0.857 | 0.857 | 0.571 (was 0.143) |
| Bid recall | 1.0 | 0.0 | 1.0 |
| Scam skipped (1 job) | 1/1 | 1/1 | 1/1 (was 0/1) |
| Injection skipped (1 job) | 1/1 | 1/1 | 1/1 (was 0/1) |
| Scam flags on non-scams | 0 | 2 | 1 |
| Jobs with an unapproved write | 0 | 0 | 0 (writes only after `interrupt()`) |
| Jobs with any write-tool call | 0 | 0 | 0 |
| Mean tool calls | 2.29 | 1.71 | 5.43 |
| Mean tokens per job | 5,282 | 6,800 | n/a (no model call before the decision) |
| Latency p50 / p95 (s) | 20.7 / 48.1 | 29.1 / 101.0 | n/a (see below) |

**The graph row.** The first run bid on all 7 jobs (accuracy 0.143). That was real behaviour of
the shipped nodes, not a harness artefact:
- The Fit Matcher counted a requirement as covered whenever `search_evidence` returned any item.
  Dense search always returns items, so the fit score was always 1.0.
- The Risk Assessor's config regexes scored the cheque scam (job-00219) at 0.0 and the injection
  post (job-00337) at 0.3, both under the 0.70 skip threshold.

**Fix, then rerun of the graph arm only** (the baselines' rows are cached and unchanged):
- A requirement now counts as covered only when its best evidence scores at least
  `thresholds.minimum_evidence_score` (0.65). The threshold was chosen on 80 other dev jobs
  (`evals/results/fit_threshold_dev.json`): 78% of bid jobs still reach fit 0.6, against 46% of
  skip jobs (100% of both before).
- Two generic risk signals in config: a fake-cheque/overpayment pattern, and injected
  instructions aimed at AI writers ("requirement for AI-written proposals ...").
Result: accuracy 0.571; the scam and the injection are skipped; the bid job is still bid. It still
bids on 3 of the 4 "other skip" jobs, which are mostly skips for budget or domain reasons that
fit and risk alone do not see. The fix was tuned after seeing these 7 jobs, so this rerun is
not an unbiased estimate; a larger, untouched sample is needed.

Its 0 tokens and about 0.3 s per job are measured, but they are not comparable with the
baselines, because no model runs on its triage path. They are shown as n/a above.

## Findings
- On these 7 jobs both LLM baselines judged better than our rule-based triage, even after the
  fix (0.857 vs 0.571). The graph's remaining errors are budget and domain skips; a model
  judgement in the Fit Matcher or Pricing step is the next thing to try.
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
