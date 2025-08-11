# cogni_health_proto

Prototype FastAPI backend integrating with the Fitbit Web API.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload

Endpoints
GET /health → {"status":"ok"}

GET /docs → Swagger UI

License
MIT — see LICENSE.
