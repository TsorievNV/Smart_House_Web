"""Cookie-сессии; пользователь и TTL хранятся в Redis."""
import re
import secrets
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated
from fastapi import Depends, HTTPException
from fastapi.security import APIKeyCookie
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession
from core.config import ROOT, settings
from db.session import get_db
from models import User

cookie = APIKeyCookie(name=settings.SESSION_COOKIE_NAME, auto_error=False,
                      description="Cookie устанавливается POST /api/users/login; браузер отправляет её автоматически.")
SessionToken = Annotated[str | None, Depends(cookie)]

@dataclass(frozen=True)
class CurrentUser:
    id: int | None = None
    username: str | None = None

@lru_cache(maxsize=1)
def get_sessions() -> Redis:
    return Redis.from_url(settings.REDIS_URL, decode_responses=True,
                          socket_connect_timeout=2, socket_timeout=2)

Sessions = Annotated[Redis, Depends(get_sessions)]

CREATE_SESSION_LUA = (ROOT / "core/lua/create_session.lua").read_text(encoding="utf-8")

def session_key(token: str | None) -> str | None:
    if token and re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return f"session:{token}"
    return None

async def create_session(sessions, user, previous_token=None):
    previous_key = session_key(previous_token)
    for _ in range(3):
        token = secrets.token_urlsafe(32)
        keys = [session_key(token)]
        if previous_key:
            keys.append(previous_key)
        created = await sessions.eval(
            CREATE_SESSION_LUA, len(keys), *keys,
            user.id, user.username, settings.SESSION_TTL_SECONDS,
        )
        if created == 1:
            return token
    raise RedisError("Could not allocate a unique session key")

async def resolve_user(token, sessions, db):
    key = session_key(token)
    if key is None:
        return CurrentUser()
    data = await sessions.hgetall(key)
    if not data or not data.get("user_id", "").isdigit():
        return CurrentUser()
    user = await db.get(User, int(data["user_id"]))
    return CurrentUser(user.id, user.username) if user else CurrentUser()

async def get_optional_user(token: SessionToken, sessions: Sessions,
                            db: Annotated[AsyncSession, Depends(get_db)]) -> CurrentUser:
    try:
        return await resolve_user(token, sessions, db)
    except RedisError:
        return CurrentUser()

async def get_current_user(token: SessionToken, sessions: Sessions,
                           db: Annotated[AsyncSession, Depends(get_db)]) -> CurrentUser:
    try:
        current = await resolve_user(token, sessions, db)
    except RedisError as exc:
        raise HTTPException(503) from exc
    if current.id is None:
        raise HTTPException(401)
    return current
