# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db import create_db_and_tables
from app.routers import biometrics
from app import auth
from fastapi.responses import RedirectResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ----
    create_db_and_tables()
    yield
    # ---- shutdown ----
    # (nothing to tear down yet)

app = FastAPI(title="cogni_health_proto", version="0.1.0", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/docs")

app.include_router(biometrics.router, prefix="/api/v1/biometrics", tags=["biometrics"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
