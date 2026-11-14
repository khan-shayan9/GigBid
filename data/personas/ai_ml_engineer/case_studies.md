# Case studies — Amina Rao (synthetic persona)

source: synthetic · document: case_studies · persona: ai_ml_engineer

## ai-cs-01 | MedAssist: answering patient questions from clinic leaflets
Client: a three-site physiotherapy clinic · 2024 · fixed price

The front desk spent most mornings answering the same questions about parking, insurance and
post-surgery exercises. I chunked their 140 leaflets, embedded them, and put a small LLM on top
that answers only from the retrieved passages and quotes the leaflet title under each answer. If
nothing relevant comes back above a similarity cut-off it says "please call reception" instead of
guessing. Ran it next to the reception inbox for two weeks before switching it on for patients.
Receptionists said phone volume about exercises dropped noticeably.

## ai-cs-02 | Getting rows out of scanned invoices
Client: accounting firm, 12 staff · 2023 · hourly

Tesseract alone mangled the totals column, so I combined OCR with a layout-aware model to pick
supplier, date, VAT and line totals, then added plain Python checks (line items must add up to
the total, dates must parse). Anything failing a check went to a review queue instead of the
ledger. Staff now review exceptions rather than typing every invoice.

```python
if abs(sum(line.amount for line in invoice.lines) - invoice.total) > 0.01:
    queue_for_review(invoice, reason="lines do not sum to total")
```

## ai-cs-03 | Who is about to cancel? Churn model for a subscription box
Client: D2C snack subscription · 2023 · fixed price

Gradient boosting on order history, skips and support tickets. The interesting part was the
label: "cancelled within 60 days" vs "paused" behaved very differently, so we modelled them
separately. Delivered SHAP explanations per customer so the retention team knew *why* someone
was flagged, plus a monthly retrain script.

## ai-cs-04 | Review sentiment for a phone accessories seller
Client: marketplace seller · 2022 · fixed price

Fine-tuned a DistilBERT model on ~8k of their own reviews (labelled with the owner over two
afternoons) to separate complaints about delivery from complaints about the product itself.
Output went into a simple weekly spreadsheet; no dashboard needed.

## ai-cs-05 | Matching CVs to open roles for a recruitment agency
Client: boutique recruitment agency · 2024 · fixed price

Recruiters were keyword-searching PDFs. I embedded CVs and job descriptions, ranked candidates
by cosine similarity, then re-ranked with a few hard filters (location, notice period). The
recruiters wanted to see why a CV ranked high, so each match lists the three CV sentences that
were closest to the job text. Lives in a small FastAPI app they call from their ATS.

## ai-cs-06 | Bakery demand forecast
Client: regional bakery chain, 9 shops · 2021 · hourly

Started with Prophet, ended with LightGBM on lagged sales, weather and school holidays because
it handled the Saturday spikes better. Forecasts per shop per product per day, exported to the
ordering sheet each evening. Waste on the worst products went down over the following quarter.

## ai-cs-07 | Spotting weaving defects on a textile line
Client: textile mill · 2022 · fixed price

Fine-tuned an object detector on photos from a camera above the loom. Most of the work was
getting consistent lighting and labelling 2,000 images with the floor supervisor. Runs on a
small edge box next to the machine and flags rolls for manual inspection; it does not stop the
line.

## ai-cs-08 | Regression tests for LLM prompts
Client: legal-tech startup · 2024 · hourly

Their contract-summary prompts kept silently changing behaviour after "small" edits. I built a
set of 120 frozen test contracts with expected key points and a scorer, so every prompt change
runs the suite in CI and shows which summaries got worse. Also added cost per run to the report.

## ai-cs-09 | Meeting notes from recorded calls
Client: consulting team · 2023 · fixed price

Whisper for transcripts, then chunked summarisation with action items pulled out as a list.
Speaker names were the hard part; we settled on the team typing names once per call instead of
automatic diarisation.

## ai-cs-10 | Course recommendations for an e-learning site
Client: online course platform · 2022 · hourly

Implicit-feedback matrix factorisation on enrolments and watch time, with a popularity fallback
for new users. A/B tested against "most popular" for a month with the client's own analytics.

## ai-cs-11 | Flagging odd payments
Client: payments startup · 2021 · hourly

Isolation forest plus a handful of hand-written rules the risk analyst already trusted. Every
flag carried the rule or feature that triggered it, because the analyst refused to act on a
black-box score.

## ai-cs-12 | From notebook to service
Client: several (template reused) · 2023 to 2024

I keep a template for turning a trained model into a FastAPI service: Docker image, health
endpoint, MLflow model registry, input validation with Pydantic, and a smoke test. Used it for
the churn model, the bakery forecast and the CV matcher.

## ai-cs-13 | Text classification coursework
Course project · 2019

Compared TF-IDF + logistic regression with a fine-tuned BERT on a news topic dataset. Mostly a
learning exercise; the write-up is on my GitHub.

## ai-cs-14 | Urdu product review baseline
Personal project · 2022

Collected and labelled about 1,500 Urdu and Roman-Urdu reviews and trained a baseline
classifier. Small, but it taught me how much cleaning mixed-script text needs.

## ai-cs-15 | Email triage agent prototype
Client: property management company · 2024 · fixed price (prototype only)

Prototype that reads incoming tenant emails, classifies them (repair, payment, complaint) and
drafts a reply using tool calls to look up the tenant's unit. Stayed a prototype: the client
decided a human must send every reply, which we built in as an approval step.

## ai-cs-16 | Four-week ML workshop
Local tech community · 2023

Ran evening sessions for 20 junior developers covering scikit-learn, evaluation and why accuracy
alone lies. Not client work, but it's where I got good at explaining models to non-specialists.
