from fastapi import APIRouter
router = APIRouter()
@router.get("/latest")

def latest():
    return {"message": "biometrics will live here"}
