# Copyright (c) 2025 Abenivate LLC
# SPDX-License-Identifier: MIT
from datetime import datetime, timedelta, timezone
import httpx
from fastapi import HTTPException
from app.config import settings
from app.models import Token

TOKEN_URL = "https://api.fitbit.com/oauth2/token"
API_BASE  = "https://api.fitbit.com"

async def _refresh(tok: Token) -> Token:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": tok.refresh_token,
        "client_id": settings.FITBIT_CLIENT_ID,
    }
    auth = (settings.FITBIT_CLIENT_ID, settings.FITBIT_CLIENT_SECRET)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(TOKEN_URL, data=data, auth=auth)
    if r.status_code != 200:
        raise HTTPException(401, detail=f"Failed to refresh Fitbit token: {r.text}")
    j = r.json()
    tok.access_token  = j["access_token"]
    tok.refresh_token = j["refresh_token"]
    tok.scope         = j.get("scope", tok.scope)
    tok.token_type    = j.get("token_type", tok.token_type)
    tok.expires_at    = datetime.now(timezone.utc) + timedelta(seconds=int(j.get("expires_in", 28800)))
    return tok

async def ensure_fresh(tok: Token, session, leeway_sec: int = 60) -> Token:
    """Refresh access token if it's near expiry; persist updated token."""
    if tok.expires_at <= datetime.now(timezone.utc) + timedelta(seconds=leeway_sec):
        tok = await _refresh(tok)
        session.add(tok)
        session.commit()
    return tok

async def authed_get(tok: Token, path: str, params: dict | None = None, accept_language: str = "en_US"):
    headers = {
        "Authorization": f"Bearer {tok.access_token}",
        "Accept": "application/json",
        "Accept-Language": accept_language,
    }
    async with httpx.AsyncClient(timeout=30, base_url=API_BASE, headers=headers) as client:
        r = await client.get(path, params=params)
    if r.status_code == 401:
        from fastapi import HTTPException
        raise HTTPException(401, detail="Unauthorized to Fitbit API")
    r.raise_for_status()
    return r.json()

def _as_aware_utc(dt: datetime) -> datetime:
    # If DB stored a naive datetime, assume it is UTC and make it aware.
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

async def ensure_fresh(tok: Token, session, leeway_sec: int = 60) -> Token:
    now_utc = datetime.now(timezone.utc)
    exp_utc = _as_aware_utc(tok.expires_at)
    if exp_utc <= now_utc + timedelta(seconds=leeway_sec):
        tok = await _refresh(tok)
        session.add(tok)
        session.commit()
    return tok