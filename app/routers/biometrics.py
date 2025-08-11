from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from app.db import get_session
from app.models import Token
from app.services.fitbit import ensure_fresh, authed_get

router = APIRouter()

@router.get("/profile")
async def profile(session=Depends(get_session)):
    tok = session.exec(select(Token)).first()
    if not tok:
        raise HTTPException(400, "No token; visit /auth/login first.")
    tok = await ensure_fresh(tok, session)
    return await authed_get(tok, "/1/user/-/profile.json")
