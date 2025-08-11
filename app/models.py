from sqlalchemy import Column, DateTime
from datetime import datetime, timedelta, timezone
from sqlmodel import SQLModel, Field

class Token(SQLModel, table=True):
    user_id: str = Field(primary_key=True)
    access_token: str
    refresh_token: str
    scope: str = ""
    token_type: str = "Bearer"
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))

    @classmethod
    def from_token_response(cls, data: dict, user_id: str):
        return cls(
            user_id=user_id,
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            scope=data.get("scope", ""),
            token_type=data.get("token_type", "Bearer"),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 28800))),
        )
