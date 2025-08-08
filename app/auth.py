import urllib.parse
from fastapi import APIRouter
from starlette.responses import RedirectResponse
from app.config import settings

router = APIRouter()

@router.get("/login")
def login():
    params = {
        "response_type": "code",
        "client_id": settings.FITBIT_CLIENT_ID,
        "redirect_uri": settings.FITBIT_REDIRECT_URI,
        "scope": "heartrate activity sleep",
    }
    url = "https://www.fitbit.com/oauth2/authorize?" + urllib.parse.urlencode(params)
    return RedirectResponse(url)
