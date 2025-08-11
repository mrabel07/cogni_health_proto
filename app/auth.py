# Copyright (c) 2025 Abenivate LLC
# SPDX-License-Identifier: MIT
import secrets, urllib.parse
import httpx
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import RedirectResponse, JSONResponse
from app.config import settings

router = APIRouter()

@router.get("/login")
def login():
    state = secrets.token_urlsafe(32)
    params = {
        "response_type": "code",
        "client_id": settings.FITBIT_CLIENT_ID,
        "redirect_uri": settings.FITBIT_REDIRECT_URI,
        "scope": "heartrate activity sleep weight profile",
        "state": state,
    }
    url = "https://www.fitbit.com/oauth2/authorize?" + urllib.parse.urlencode(params)
    resp = RedirectResponse(url)
    resp.set_cookie(
        key="fitbit_oauth_state",
        value=state,
        max_age=600,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return resp

@router.get("/callback")
async def callback(request: Request, code: str, state: str):
    # CSRF check
    if state != request.cookies.get("fitbit_oauth_state"):
        raise HTTPException(400, detail="Invalid OAuth state")

    token_url = "https://api.fitbit.com/oauth2/token"
    data = {
        "client_id": settings.FITBIT_CLIENT_ID,
        "grant_type": "authorization_code",
        "redirect_uri": settings.FITBIT_REDIRECT_URI,
        "code": code,
    }
    auth = (settings.FITBIT_CLIENT_ID, settings.FITBIT_CLIENT_SECRET)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(token_url, data=data, auth=auth)
    if r.status_code != 200:
        raise HTTPException(400, detail=f"Token exchange failed: {r.text}")
    tok = r.json()

    # Try to get user id (some responses include user_id)
    user_id = tok.get("user_id")
    if not user_id:
        headers = {"Authorization": f"Bearer {tok['access_token']}"}
        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            prof = await client.get("https://api.fitbit.com/1/user/-/profile.json")
        if prof.status_code == 200:
            user_id = prof.json()["user"]["encodedId"]

    # Clear the state cookie and return something simple for now
    resp = JSONResponse({"ok": True, "user_id": user_id, "scope": tok.get("scope", "")})
    resp.delete_cookie("fitbit_oauth_state")
    return resp
