"""Регистрация, аутентификация и отзыв серверных сессий."""
import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from redis.exceptions import RedisError
from starlette.concurrency import run_in_threadpool
from api.smart_devices import DB, reject_query
from api.schemas import UserInput, UserOutput
from models import User
from core.config import settings
from core.current_user import Sessions, SessionToken, create_session, session_key

router = APIRouter(prefix="/api/users", tags=["Пользователи"], dependencies=[Depends(reject_query)])

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"scrypt$16384$8$1${salt}${digest}"

def verify_password(password, encoded):
    try:
        scheme, n, r, p, salt, digest = encoded.split("$")
        if (scheme, n, r, p) != ("scrypt", "16384", "8", "1"):
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return secrets.compare_digest(actual, digest)
    except (AttributeError, ValueError):
        return False

DUMMY_HASH = hash_password(secrets.token_urlsafe(32))

@router.post("", response_model=UserOutput, status_code=201, summary="Регистрация пользователя",
             description="Создаёт пользователя с scrypt-хешем пароля. Повторный логин — 403. Затем выполните вход.")
async def register(payload: UserInput, db: DB):
    user = User(username=payload.username, password_hash=await run_in_threadpool(hash_password, payload.password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(403) from exc
    return user

@router.post("/login", response_model=UserOutput, summary="Вход и создание сессии Redis",
             description="Проверяет логин и пароль, возвращает пользователя и HttpOnly cookie. Lua-скрипт атомарно создаёт сессию Redis с TTL (по умолчанию 24 часа) и удаляет предыдущую сессию при повторном входе.",
             responses={401: {"description": "Неверный логин или пароль"}, 503: {"description": "Redis недоступен"}})
async def login(payload: UserInput, response: Response, db: DB, sessions: Sessions, token: SessionToken):
    user = await db.scalar(select(User).where(User.username == payload.username))
    encoded = user.password_hash if user and user.password_hash else DUMMY_HASH
    valid = await run_in_threadpool(verify_password, payload.password, encoded)
    if not user or not user.password_hash or not valid:
        raise HTTPException(401)
    try:
        new_token = await create_session(sessions, user, token)
    except RedisError as exc:
        raise HTTPException(503) from exc
    response.set_cookie(settings.SESSION_COOKIE_NAME, new_token, max_age=settings.SESSION_TTL_SECONDS,
                        httponly=True, secure=settings.SESSION_COOKIE_SECURE, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return user

@router.post("/logout", status_code=200, response_class=Response, summary="Выход и удаление сессии",
             description="Удаляет текущую сессию из Redis и cookie браузера. Повторный выход допустим.",
             responses={503: {"description": "Redis недоступен"}})
async def logout(sessions: Sessions, token: SessionToken):
    key = session_key(token)
    if key:
        try:
            await sessions.delete(key)
        except RedisError as exc:
            raise HTTPException(503) from exc
    response = Response(status_code=200, headers={"Cache-Control": "no-store"})
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/", httponly=True,
                           secure=settings.SESSION_COOKIE_SECURE, samesite="lax")
    return response
