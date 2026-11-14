# cv-matcher

source: synthetic · document: repo_readme · persona: ai_ml_engineer

Rank candidate CVs against a job description and explain each match.

- Embeds CV sentences and the job text, scores candidates by their best-matching sentences.
- Hard filters (location, notice period) applied after ranking.
- `/match` endpoint returns the top candidates plus the 3 CV sentences that drove each score.

Built for a recruitment agency that plugs it into their ATS through a webhook.

```bash
uvicorn app:app --port 8080
curl -X POST localhost:8080/match -d @job.json
```
