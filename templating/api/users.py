"""Регистрация; аутентификация и деавторизация — заглушки для ЛР4."""
import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from api.smart_devices import DB, reject_query
from api.schemas import UserInput, UserOutput
from models import User

router = APIRouter(prefix="/api/users", tags=["Пользователи"], dependencies=[Depends(reject_query)])

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"scrypt$16384$8$1${salt}${digest}"

@router.post("", response_model=UserOutput, status_code=201)
async def register(payload: UserInput, db: DB):
    user = User(username=payload.username, password_hash=await run_in_threadpool(hash_password, payload.password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(403) from exc
    return user

@router.post("/login", status_code=200, response_class=Response)
async def login():
    return Response(status_code=200)

@router.post("/logout", status_code=200, response_class=Response)
async def logout():
    return Response(status_code=200)
