# Copyright (c) 2025 Abenivate LLC
# SPDX-License-Identifier: MIT

from datetime import date, timedelta, datetime
from typing import List, Dict
from fastapi import HTTPException
from app.services.fitbit import authed_get, ensure_fresh
from sqlmodel import select, delete, SQLModel, Session
from app.models import IntradayMinute, Token

def _make_ts(day_str: str, time_str: str) -> datetime:
    # Fitbit intraday times are "HH:MM:SS" in the user's local day
    return datetime.fromisoformat(f"{day_str}T{time_str}")

async def fetch_steps_and_hr_minute(session, tok: Token, day_str: str) -> List[Dict]:
    """
    Pull 1-minute intraday steps and heart rate, align by HH:MM:SS, and return rows:
    [{ "time": "08:31:00", "steps": 5, "hr": 78 }, ...]
    """
    tok = await ensure_fresh(tok, session)

    steps = await authed_get(tok, f"/1/user/-/activities/steps/date/{day_str}/1d/1min.json")
    hr    = await authed_get(tok, f"/1/user/-/activities/heart/date/{day_str}/1d/1min.json")

    steps_ds = {d["time"]: d["value"] for d in steps.get("activities-steps-intraday", {}).get("dataset", [])}
    hr_ds    = {d["time"]: d["value"] for d in hr.get("activities-heart-intraday", {}).get("dataset", [])}

    times = sorted(set(steps_ds.keys()) | set(hr_ds.keys()))
    return [{"time": t, "steps": steps_ds.get(t, 0), "hr": hr_ds.get(t)} for t in times]

def store_intraday_rows(session: Session, user_id: str, day_str: str, rows: List[Dict]) -> int:
    # wipe-and-write per day keeps logic simple
    session.exec(delete(IntradayMinute).where(
        (IntradayMinute.user_id == user_id) & (IntradayMinute.day == datetime.fromisoformat(day_str).date())
    ))
    objects = [
        IntradayMinute(
            user_id=user_id,
            ts=_make_ts(day_str, r["time"]),
            day=datetime.fromisoformat(day_str).date(),
            steps=r.get("steps"),
            hr=r.get("hr"),
        )
        for r in rows
    ]
    session.add_all(objects)
    session.commit()
    return len(objects)

def load_intraday_rows(session: Session, user_id: str, day_str: str) -> List[Dict]:
    day_d = datetime.fromisoformat(day_str).date()
    q = select(IntradayMinute).where(
        (IntradayMinute.user_id == user_id) & (IntradayMinute.day == day_d)
    ).order_by(IntradayMinute.ts)
    rows = session.exec(q).all()
    return [
        {"time": r.ts.strftime("%H:%M:%S"), "steps": r.steps, "hr": r.hr}
        for r in rows
    ]
