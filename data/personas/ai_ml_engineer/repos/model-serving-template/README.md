# model-serving-template

source: synthetic · document: repo_readme · persona: ai_ml_engineer

My starting point for shipping a trained model as an HTTP service.

Includes: FastAPI app with Pydantic request models, `/health`, model loading from the MLflow
registry, a Dockerfile, and a pytest smoke test that calls `/predict` with a fixture row.

Used for: subscription churn scoring, bakery demand forecasts, CV matching.
