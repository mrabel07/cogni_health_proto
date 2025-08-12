# Copyright (c) 2025 Abenivate LLC
# SPDX-License-Identifier: MIT

from datetime import date, timedelta
from io import BytesIO
from typing import Optional
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from sqlmodel import select
from app.db import get_session
from app.models import Token
from app.services.timeseries import (
    fetch_steps_and_hr_minute,
    store_intraday_rows,
    load_intraday_rows,
)

router = APIRouter()

def _get_single_token(session):
    """Return the single stored Fitbit token (prototype assumes one user)."""
    tok = session.exec(select(Token)).first()
    if not tok:
        raise HTTPException(400, "No Fitbit token stored; visit /auth/login first.")
    return tok

def _resolve_day(s: str) -> str:
    if s == "today": return date.today().strftime("%Y-%m-%d")
    if s == "yesterday": return (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    return s  # assume YYYY-MM-DD

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
    
@router.get("/motion-heart")
async def motion_heart_json(
    day: str = Query("today", pattern=r"^(today|yesterday|\d{4}-\d{2}-\d{2})$"),
    session=Depends(get_session),
):
    tok = _get_single_token(session)
    rows = await fetch_steps_and_hr_minute(session, tok, _resolve_day(day))
    return JSONResponse({"day": _resolve_day(day), "points": rows})

@router.get("/charts/motion-heart.png")
async def motion_heart_chart(
    day: str = Query("today", pattern=r"^(today|yesterday|\d{4}-\d{2}-\d{2})$"),
    session=Depends(get_session),
):
    tok = _get_single_token(session)
    rows = await fetch_steps_and_hr_minute(session, tok, _resolve_day(day))
    if not rows:
        raise HTTPException(404, "No data for that date")

    # Build arrays for plotting
    x = list(range(len(rows)))                     # 0..N-1 (avoid huge tick labels)
    steps = [r["steps"] for r in rows]
    hr    = [r["hr"] if r["hr"] is not None else float("nan") for r in rows]

    # Plot (distinct colors + legend)
    fig = plt.figure(figsize=(10, 4))
    ax1 = plt.gca()

    # Steps/min on left axis
    l1, = ax1.plot(x, steps, label="Steps/min", color="tab:blue", linewidth=1)
    ax1.set_xlabel(f"Minutes of {_resolve_day(day)}")
    ax1.set_ylabel("Steps/min", color="tab:blue")
    ax1.tick_params(axis="y", labelcolor="tab:blue")

    # Heart rate on right axis
    ax2 = ax1.twinx()
    l2, = ax2.plot(x, hr, label="Heart rate (bpm)", color="tab:red", linewidth=1)
    ax2.set_ylabel("Heart rate (bpm)", color="tab:red")
    ax2.tick_params(axis="y", labelcolor="tab:red")

    # Legend (combine handles from both axes)
    lines = [l1, l2]
    labels = [ln.get_label() for ln in lines]
    ax1.legend(lines, labels, loc="upper left", frameon=False)

    ax1.grid(True, linestyle="--", alpha=0.3)
    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

@router.post("/ingest/motion-heart")
async def ingest_motion_heart(
    day: str = Query("today", pattern=r"^(today|yesterday|\d{4}-\d{2}-\d{2})$"),
    session=Depends(get_session),
):
    tok = _get_single_token(session)
    day = _resolve_day(day)
    rows = await fetch_steps_and_hr_minute(session, tok, day)
    count = store_intraday_rows(session, tok.user_id, day, rows)
    return {"ok": True, "day": day, "stored": count}

@router.get("/motion-heart.db")
async def motion_heart_from_db(
    day: str = Query("today", pattern=r"^(today|yesterday|\d{4}-\d{2}-\d{2})$"),
    session=Depends(get_session),
):
    tok = _get_single_token(session)
    day = _resolve_day(day)
    rows = load_intraday_rows(session, tok.user_id, day)
    if not rows:
        raise HTTPException(404, "No cached data for that date")
    return {"day": day, "points": rows}

@router.get("/charts/motion-heart.db.png")
async def motion_heart_chart_from_db(
    day: str = Query("today", pattern=r"^(today|yesterday|\d{4}-\d{2}-\d{2})$"),
    session=Depends(get_session),
):
    tok = _get_single_token(session)
    day = _resolve_day(day)
    rows = load_intraday_rows(session, tok.user_id, day)
    if not rows:
        raise HTTPException(404, "No cached data for that date")

    x = list(range(len(rows)))
    steps = [r["steps"] or 0 for r in rows]
    hr    = [r["hr"] if r["hr"] is not None else float("nan") for r in rows]

    fig = plt.figure(figsize=(10, 4))
    ax1 = plt.gca()

    l1, = ax1.plot(x, steps, label="Steps/min", color="tab:blue", linewidth=1)
    ax1.set_xlabel(f"Minutes of {day}")
    ax1.set_ylabel("Steps/min", color="tab:blue")
    ax1.tick_params(axis="y", labelcolor="tab:blue")

    ax2 = ax1.twinx()
    l2, = ax2.plot(x, hr, label="Heart rate (bpm)", color="tab:red", linewidth=1)
    ax2.set_ylabel("Heart rate (bpm)", color="tab:red")
    ax2.tick_params(axis="y", labelcolor="tab:red")

    lines = [l1, l2]
    labels = [ln.get_label() for ln in lines]
    ax1.legend(lines, labels, loc="upper left", frameon=False)

    ax1.grid(True, linestyle="--", alpha=0.3)
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

@router.api_route("/ingest/motion-heart", methods=["GET", "POST"])
async def ingest_motion_heart(
    day: str = Query("today", pattern=r"^(today|yesterday|\d{4}-\d{2}-\d{2})$"),
    session=Depends(get_session),
):
    tok = _get_single_token(session)
    day = _resolve_day(day)
    rows = await fetch_steps_and_hr_minute(session, tok, day)
    count = store_intraday_rows(session, tok.user_id, day, rows)
    return {"ok": True, "day": day, "stored": count}