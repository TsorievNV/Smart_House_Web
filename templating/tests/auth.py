"""HTTP-проверки ЛР4: PostgreSQL, настоящий Redis, подмена только MinIO.

DB_NAME=smart_traffic_lab4_test PYTHONPATH=. ../venv/bin/python tests/auth.py
Нужна отдельная пустая БД *_test с применёнными миграциями Alembic.
Тестовые записи остаются в этой БД после запуска.
Redis должен быть доступен по REDIS_URL. Удаляются только созданные тестом сессии.
"""
import asyncio
from unittest.mock import AsyncMock
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, func
from redis.exceptions import ConnectionError as RedisConnectionError
from main import app
from db.session import get_db
from core.config import settings
from core.current_user import get_sessions, session_key
from core.storage import get_storage
from models import SmartDevice, User, Like

async def main():
    if not settings.DB_NAME.endswith("_test"):
        raise RuntimeError("Use an isolated *_test PostgreSQL database")
    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        for model in (User, SmartDevice, Like):
            if await db.scalar(select(func.count()).select_from(model)):
                await engine.dispose()
                raise RuntimeError("Test database must be empty; existing data will not be deleted")
    async def database():
        async with factory() as session:
            yield session
    storage = AsyncMock()
    storage.save.side_effect = ["test/image.jpg", "test/video.mp4"]
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_storage] = lambda: storage
    sessions = get_sessions()
    keys = set()
    checks = 0
    credentials = {"username": "lab4_owner", "password": "Lab4 password 123"}
    try:
        await sessions.ping()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            async def request(method, path, status=200, **kwargs):
                nonlocal checks
                result = await client.request(method, path, **kwargs)
                assert result.status_code == status, (path, result.status_code, result.text)
                if result.status_code >= 400:
                    assert result.content == b""
                checks += 1
                return result
            async def login(payload=credentials):
                result = await request("POST", "/api/users/login", json=payload)
                token = client.cookies[settings.SESSION_COOKIE_NAME]
                keys.add(session_key(token))
                assert "HttpOnly" in result.headers["set-cookie"]
                assert "SameSite=lax" in result.headers["set-cookie"]
                assert "password_hash" not in result.json()
                return token
            await request("GET", "/api/smart_devices")
            owner = (await request("POST", "/api/users", 201, json=credentials)).json()
            await request("POST", "/api/users", 403, json=credentials)
            await request("POST", "/api/users/login", 401, json={**credentials, "password": "wrong password"})
            await request("POST", "/api/users/login", 401, json={**credentials, "username": "unknown"})
            await request("PUT", "/api/smart_devices/1/publication", 401)
            await request("GET", "/api/smart_devices/draft", 401)
            await request("POST", "/api/smart_devices/1/likes", 401, json={"value": 1})
            await request("DELETE", "/api/smart_devices/1", 401)
            token = await login()
            assert (await sessions.hgetall(session_key(token)))["username"] == credentials["username"]
            assert 0 < await sessions.ttl(session_key(token)) <= settings.SESSION_TTL_SECONDS
            previous = token
            token = await login()
            assert token != previous and not await sessions.exists(session_key(previous))
            data = dict(title="ЛР4", description="Услуга", traffic_mean="10", traffic_variance="2")
            files = {"image": ("image.jpg", b"test", "image/jpeg"), "video": ("video.mp4", b"test", "video/mp4")}
            await request("POST", "/api/smart_devices", 404, data={**data, "creator_id": "99"}, files=files)
            created = (await request("POST", "/api/smart_devices", 201, data=data, files=files)).json()
            assert created["creator_id"] == owner["id"] and created["formed_at"] is None
            did = created["id"]
            client.cookies.clear()
            await request("PUT", f"/api/smart_devices/{did}/publication", 401)
            other = {**credentials, "username": "lab4_other"}
            await request("POST", "/api/users", 201, json=other)
            await login(other)
            await request("PUT", f"/api/smart_devices/{did}/publication", 403)
            client.cookies.clear()
            # Ручной перенос Cookie, как из браузера в Postman.
            header = {"Cookie": f"{settings.SESSION_COOKIE_NAME}={token}"}
            published = (await request("PUT", f"/api/smart_devices/{did}/publication", headers=header)).json()
            assert published["formed_at"] and published["creator_id"] == owner["id"]
            assert published["created_at"] == created["created_at"]
            async with factory() as db:
                assert (await db.get(SmartDevice, did)).status == "published"
            for value in (None, "invalid", "A" * 43, token):
                headers = {} if value is None else {"Cookie": f"{settings.SESSION_COOKIE_NAME}={value}"}
                cards = (await request("GET", "/api/smart_devices", headers=headers)).json()
                assert [d["id"] for d in cards] == [did]
                assert cards[0]["is_owner"] == int(value == token)
            broken = AsyncMock()
            broken.hgetall.side_effect = RedisConnectionError()
            app.dependency_overrides[get_sessions] = lambda: broken
            await request("GET", "/api/smart_devices", headers=header)
            await request("PUT", f"/api/smart_devices/{did}/publication", 503, headers=header)
            app.dependency_overrides.pop(get_sessions)
            await request("POST", "/api/users/logout", headers=header)
            assert not await sessions.exists(session_key(token))
            await request("PUT", f"/api/smart_devices/{did}/publication", 401, headers=header)
            await request("POST", "/api/users/logout")
            token = await login()
            await sessions.pexpire(session_key(token), 1)
            await asyncio.sleep(0.02)
            await request("GET", "/api/smart_devices")
            await request("GET", "/api/smart_devices/draft", 401)
            schema = (await request("GET", "/openapi.json")).json()
            assert {} in schema["paths"]["/api/smart_devices"]["get"]["security"]
            publication = schema["paths"]["/api/smart_devices/{device_id}/publication"]["put"]
            assert publication["security"] == [{"APIKeyCookie": []}]
            assert "401" in publication["responses"]
            assert schema["components"]["securitySchemes"]["APIKeyCookie"]["in"] == "cookie"
        print(f"PASS: {checks} HTTP checks; Redis TTL/rotation/logout, guest/owner/foreign publication, creator, public list, OpenAPI")
    finally:
        app.dependency_overrides.clear()
        if keys:
            await sessions.delete(*keys)
        await sessions.aclose()
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
