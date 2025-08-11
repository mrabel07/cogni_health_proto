# Copyright (c) 2025 Abenivate LLC
# SPDX-License-Identifier: MIT

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from app.db import get_session
from app.models import Token
from app.services.fitbit import ensure_fresh, authed_get

router = APIRouter()

def _get_single_token(session):
    """Return the single stored Fitbit token (prototype assumes one user)."""
    tok = session.exec(select(Token)).first()
    if not tok:
        raise HTTPException(400, "No Fitbit token stored; visit /auth/login first.")
    return tok

@router.get("/profile")
async def profile(session=Depends(get_session)):
    tok = _get_single_token(session)
    tok = await ensure_fresh(tok, session)
    return await authed_get(tok, "/1/user/-/profile.json")

@router.get("/sleep")
async def sleep_by_date(
    day: str = Query("today", pattern=r"^(today|yesterday|\d{4}-\d{2}-\d{2})$"),
    session=Depends(get_session),
):
    tok = _get_single_token(session)
    tok = await ensure_fresh(tok, session)
    if day == "today":
        day = date.today().strftime("%Y-%m-%d")
    elif day == "yesterday":
        day = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    return await authed_get(tok, f"/1.2/user/-/sleep/date/{day}.json")

@router.get("/steps")
async def steps_by_date(
    day: str = Query("today", pattern=r"^(today|yesterday|\d{4}-\d{2}-\d{2})$"),
    session=Depends(get_session),
):
    tok = _get_single_token(session)
    tok = await ensure_fresh(tok, session)
    # Normalize day -> explicit YYYY-MM-DD for reliability
    if day == "today":
        day = date.today().strftime("%Y-%m-%d")
    elif day == "yesterday":
        day = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Option A: daily summary (broad info)
    try:
        return await authed_get(tok, f"/1/user/-/activities/date/{day}.json")
    except Exception:
        # Option B: time-series (often more forgiving)
        return await authed_get(tok, f"/1/user/-/activities/steps/date/{day}/1d.json")

@router.get("/heart/today")
async def heart_today(session=Depends(get_session)):
    """
    Returns today's heart data.
    - First tries intraday 1-sec series (requires heartrate scope; intraday works for Personal apps on your own data).
    - Falls back to daily summary if intraday not available.
    """
    tok = _get_single_token(session)
    tok = await ensure_fresh(tok, session)
    try:
        # Intraday (1-second resolution)
        return await authed_get(tok, "/1/user/-/activities/heart/date/today/1d/1sec.json")
    except HTTPException:
        # Daily summary fallback
        return await authed_get(tok, "/1/user/-/activities/heart/date/today/1d.json")