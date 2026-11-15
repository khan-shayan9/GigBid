| Variant | Evidence Recall@5 | nDCG@10 | MRR | Unsupported claims per proposal (before -> after verification) | Judge score (1-5) | GigSim reply rate | p95 latency (s) | Cost per proposal (USD) |
|---|---|---|---|---|---|---|---|---|
| v0 | 0.2194 | 0.2706 | 0.2849 | 0.333 -> 0.0 | 2.75 | 0.5556 | 65.552 | n/m |
| v2 | 0.2583 | 0.3071 | 0.3163 | n/m | n/m | n/m | n/m | n/m |
| v3 | 0.2417 | 0.2812 | 0.3243 | n/m | n/m | n/m | n/m | n/m |
| v1 | 0.2972 | 0.3552 | 0.4122 | 0.444 -> 0.222 | 3.0 | 0.5556 | 74.896 | n/m |
| v8 | 0.1167 | 0.1391 | 0.1828 | n/m | n/m | n/m | n/m | n/m |
| v1_v2 | 0.2944 | 0.3279 | 0.3545 | n/m | n/m | n/m | n/m | n/m |
| v1_v2_v3 | 0.2417 | 0.3453 | 0.3791 | n/m | n/m | n/m | n/m | n/m |

Judge: the judge is **not yet calibrated** (no hand labels yet).
Sources: `evals/results/rag_retrieval_dev.json`, `evals/results/proposal_eval_dev.json`, `evals/results/judge_calibration.json`.
