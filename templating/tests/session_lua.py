"""PYTHONPATH=. ../venv/bin/python tests/session_lua.py — нужен настоящий Redis."""
import asyncio
import secrets
from types import SimpleNamespace
from unittest.mock import patch

from redis.exceptions import ResponseError
from core.current_user import CREATE_SESSION_LUA, create_session, get_sessions, session_key
from core.config import settings


async def main():
    sessions = get_sessions()
    keys = set()
    user = SimpleNamespace(id=2147483647, username="lua_session_test")
    try:
        token = await create_session(sessions, user)
        old_key = session_key(token)
        keys.add(old_key)
        assert await sessions.hgetall(old_key) == {
            "user_id": str(user.id), "username": user.username,
        }
        assert 0 < await sessions.ttl(old_key) <= settings.SESSION_TTL_SECONDS

        # Ошибка параметра не удаляет старую сессию и не оставляет новую без TTL.
        candidate = session_key(secrets.token_urlsafe(32))
        keys.add(candidate)
        try:
            await sessions.eval(CREATE_SESSION_LUA, 2, candidate, old_key, user.id, user.username, 0)
        except ResponseError:
            pass
        else:
            raise AssertionError("Invalid TTL accepted")
        assert await sessions.exists(old_key) and not await sessions.exists(candidate)

        # Коллизия ключа приводит к повторной генерации, а не перезаписи сессии.
        replacement = secrets.token_urlsafe(32)
        keys.add(session_key(replacement))
        with patch("core.current_user.secrets.token_urlsafe", side_effect=[token, replacement]):
            assert await create_session(sessions, user, token) == replacement
        assert not await sessions.exists(old_key)
        assert (await sessions.hgetall(session_key(replacement)))["username"] == user.username

        # Одновременные запросы с одним новым ключом: только один создаёт сессию.
        results = await asyncio.gather(*[
            sessions.eval(CREATE_SESSION_LUA, 1, candidate, user.id, user.username, 60)
            for _ in range(2)
        ])
        assert sorted(results) == [0, 1]
        assert 0 < await sessions.ttl(candidate) <= 60
        print("PASS: Lua session data/TTL, rotation, invalid TTL, collision retry, concurrent creation")
    finally:
        if keys:
            await sessions.delete(*keys)
        await sessions.aclose()


if __name__ == "__main__":
    asyncio.run(main())
