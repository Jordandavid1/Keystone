from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Any

app = FastAPI(title='KEYSTONE API', version='2.0.0-alpha.0')

class PlanRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    answers: dict[str, Any] = {}
    options: dict[str, Any] = {}

@app.get('/v1/health')
def health():
    return {'status': 'ok', 'product': 'KEYSTONE'}

@app.post('/v1/plan', status_code=501)
def plan(_: PlanRequest):
    return {'status': 'contract_scaffolded', 'detail': 'Wire the preserved JS prompt-engine through the service bridge.'}
