# clinic-faq-bot

source: synthetic · document: repo_readme · persona: ai_ml_engineer

Answers patient questions using only the clinic's own documents. Every answer cites its source
leaflet. If retrieval confidence is low the bot hands over to reception.

## How it works
1. `ingest.py` splits leaflets into ~300-token chunks and stores embeddings in Postgres
   (pgvector).
2. On a question, the top 5 chunks above `MIN_SIMILARITY` are passed to the model with a
   strict "answer only from context" instruction.
3. The response includes the leaflet titles that were used.

## Run
```bash
docker compose up
python ingest.py --folder leaflets/
```

## Notes
- No patient data is stored; questions are logged with names and phone numbers masked.
- Evaluated on 60 real front-desk questions written down by reception staff.
