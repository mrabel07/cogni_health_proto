from fastapi import FastAPI
from app.routers import biometrics
from app import auth
app = FastAPI(title="cogni_health_proto", version="0.1.0")
@app.get("/health")
def health():
    return {"status": "ok"}
# wire routes
app.include_router(biometrics.router, prefix="/api/v1/biometrics", tags=["biometrics"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
