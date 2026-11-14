# survey-weighting

source: synthetic · document: repo_readme · persona: data_analyst

Rake survey responses to known population margins (age band, region, gender) and report
weighted percentages with confidence intervals.

Why: the raw sample over-represented city respondents, which flipped two headline findings.

```bash
python rake.py responses.csv margins.json --out weighted.csv
```
