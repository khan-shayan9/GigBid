# source: synthetic · persona: ai_ml_engineer · repo: model-serving-template
import mlflow.pyfunc
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()
model = mlflow.pyfunc.load_model("models:/churn/Production")


class Customer(BaseModel):
    orders_last_90d: int = Field(ge=0)
    skips_last_90d: int = Field(ge=0)
    tickets_last_90d: int = Field(ge=0)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/predict")
def predict(customer: Customer) -> dict:
    score = float(model.predict(pd.DataFrame([customer.model_dump()]))[0])
    return {"churn_probability": score}
