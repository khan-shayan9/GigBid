# R&D question B: which retrieval design ships

## 1. Hypothesis (written 2026-11-15, before any Part B evaluation run)

This section was written before the runs. It is committed in the same commit as the results.

**H1.** Requirement decomposition plus hybrid retrieval (V1 + V2) raises evidence Recall@5 by at
least 10 points over V0 on dev jobs that list four or more skills.

**H2.** Cross-encoder reranking (V3) on top of that pipeline raises MRR by at least 0.05.

**Prediction about outcomes.** Better retrieval will raise the GigSim reply rate less than it
raises Recall@5. A simulated client decides on its own hidden preferences (must-have skills, a
budget ceiling, a dislike of generic openings). Retrieval helps with only the first of these.

**Known bias, stated in advance.** The gold evidence for each job was generated from keyword
matches between the job text and each case study (`data/pipeline/`). Lexical retrieval (BM25,
in V2) therefore has a built-in advantage on this metric. A V2 gain is partly a property of how
the labels were made, so we report it as such and do not treat it as proof that V2 finds better
evidence.

## 2. Method

- **Metrics.** Recall@5, MRR and nDCG@10 per project. Gold names case studies, so each retrieved
  item counts as its project: a review counts as the case study it reviews. Repeats are dropped
  (`evals/runners/rag_eval.py`).
- **Splits.** We tune on dev only. The held-out split is to be run once, for V0 and the shipped
  variant; it has not been run yet (§5).
- **Ablation.** Starting from the full V1 + V2 + V3 pipeline, we remove one component at a time
  (`evals/runners/ablation.py`).
- **Breakdowns.** By persona; by job kind (real, scam, duplicate, injection); own-domain versus
  off-domain; and fewer than four versus four or more listed skills.

## 3. Results (dev split)

Every number below is in `evals/results/rag_retrieval_dev.json`, `rag_ablation_dev.json` or
`proposal_eval_dev.json`. The table regenerates with `make eval-table`.

**Sample.** We used a fixed sample of 20 dev jobs with gold evidence per persona (60 scored jobs)
plus all 42 dev jobs with no gold evidence. Reranking with `bge-reranker-v2-m3` would have taken
hours on the dev CPU, so we used MiniLM-L-12 instead (ADR 0005). With n = 60, differences of
0.02 to 0.04 are within noise.

### 3.1 Retrieval

| Variant | Recall@5 | MRR | nDCG@10 | Recall@5, ≥4 skills | p95 latency (s) |
|---|---|---|---|---|---|
| V0 dense | 0.219 | 0.285 | 0.271 | 0.178 | 1.58 |
| V1 decomposition | **0.297** | **0.412** | **0.355** | 0.243 | 3.33 |
| V2 hybrid | 0.258 | 0.316 | 0.307 | 0.210 | 1.30 |
| V3 rerank | 0.242 | 0.324 | 0.281 | 0.210 | 5.27 |
| V8 corrective | 0.117 | 0.183 | 0.139 | 0.098 | 3.54 |
| V1 + V2 | 0.294 | 0.355 | 0.328 | 0.250 | 0.66 |
| V1 + V2 + V3 | 0.242 | 0.379 | 0.345 | 0.217 | 15.82 |

Latency covers retrieval only. V0, V2, V3, V1 and V8 ran first, with live model and reranker
calls. V1 + V2 and V1 + V2 + V3 ran later and reused V1's cached decompositions, so their
latency leaves out the model call and is not comparable.

**H1 is not supported.** On jobs with four or more skills, V1 + V2 scores 0.250 against V0's
0.178. That is +7.2 points, short of the predicted +10.

**H2 is not supported.** Reranking on top of V1 + V2 raises MRR by only 0.025 (0.355 to 0.379),
and Recall@5 falls from 0.294 to 0.242. A likely reason is that MiniLM-L-12 truncates its input
at 512 tokens, which cuts the chunk short when the query is long. It is also an MS MARCO
web-search model, not one trained on portfolio text.

**V1 versus V0, job by job (Recall@5).** V1 wins on 15 jobs, loses on 5 and ties on 40. The gain
comes from data_analyst (0.283 to 0.475) and ai_ml_engineer (0.150 to 0.217). fullstack_dev goes
slightly down (0.225 to 0.200). By job kind, real jobs go from 0.163 to 0.247 and injection posts
from 0.222 to 0.444. Off-domain jobs are unchanged (0.583).

**V8 is a negative result.** With an untuned threshold (MiniLM score ≥ 0), it refused evidence on
24 of the 60 jobs that have gold evidence. It refused on only 17 of the 42 jobs that have none.
So the refusal signal does not separate jobs the persona should skip from jobs it should bid on.

**Gold-label bias.** As stated in advance, gold evidence comes from keyword matches. V2's gain
over V0 (+3.9 points) is partly a property of the labels.

### 3.2 Ablation of the full pipeline (V1 + V2 + V3)

| Pipeline | Recall@5 | MRR | nDCG@10 |
|---|---|---|---|
| V1 + V2 + V3 (full) | 0.242 | 0.379 | 0.345 |
| without decomposition (V2 + V3) | 0.278 | 0.384 | 0.328 |
| without hybrid (V1 + V3) | 0.256 | 0.370 | 0.351 |
| without reranking (V1 + V2) | 0.294 | 0.355 | 0.328 |

Removing the reranker gives the best Recall@5 of the four. In this pipeline the MiniLM
reranker reorders evidence in a way that loses gold projects from the top 5. Decomposition
helps only without the reranker: V1 alone scores 0.297, but with V3 added it scores 0.256.
The latencies in `rag_ablation_dev.json` are lower than in the retrieval run because the
reranker scores were cached by then. Compare latency from `rag_retrieval_dev.json` only.

### 3.3 Proposals, verification and GigSim outcomes

For each variant we ran 9 dev jobs labelled "bid" (3 per persona). The writer was
gpt-oss-120b, the verifier gpt-oss-120b and the judge qwen3.8-27b. Each variant got a fresh
GigSim with rule-based clients, and both variants placed the same bid on each job.

| Variant | Unsupported claims per proposal (before → after verification) | Unsupported-claim rate (before → after) | Judge (1–5, uncalibrated) | GigSim reply rate | Hire rate | Tokens per proposal |
|---|---|---|---|---|---|---|
| V0 | 0.33 → 0.00 | 4.0% → 0.0% | 2.75 (1 reply unparsed) | 0.556 | 0.222 | 10,037 |
| V1 | 0.44 → 0.22 | 6.6% → 3.6% | 3.00 | 0.556 | 0.222 | 8,898 |

**Better retrieval did not raise the reply rate.** Both variants got 5 of 9 replies, on the
same jobs. Only two jobs changed outcome, each between interview and hired. This was
predicted in §1. The simulated client scores four things: a personal opening, must-have
skills named in the letter, the bid against its budget ceiling, and its own reply propensity.
Evidence quality changes only the second, and the writer likely names the job's skills whether
or not it retrieved evidence for them. The bids were identical across variants. With 9 jobs, a
one-job difference would also be noise.

**Verification removed claims, but not all of them.** Unsupported claims per proposal fell from
0.33 to 0 (V0) and from 0.44 to 0.22 (V1). In V1, two claims the verifier left in were then
flagged when it graded the cleaned draft again, so a second pass would help.

## 4. Decision: what ships

We ship **V1** (`rag.variant: v1`). It is best on all three retrieval metrics. Adding hybrid
retrieval or reranking either did not help or hurt, and reranking cost five times the latency.
In the agent, V1's requirement split belongs to the caller. `search_evidence` searches one
requirement at a time. Today the writer splits a job into its title plus its listed skills. The
Phase 5 Job Analyst replaces that with LLM decomposition, which is what V1 measures here.

## 5. Limits

- Small samples: 60 jobs for retrieval and 9 jobs per variant for proposals.
- Not yet run: the held-out split, and the full dev set for V0, V1 and V2.
- The judge is uncalibrated until the user labels 30 items (`evals/runners/judge_calibration.py`).
- "After verification" is graded by the same verifier that removed the claims.
- Proposal latency includes Groq rate-limit waits on the free tier.
- USD is blank until prices are filled in config.
