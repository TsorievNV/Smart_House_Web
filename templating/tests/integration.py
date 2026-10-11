"""Реальные PostgreSQL + MinIO. Только пустая *_test БД и отдельный *-test bucket.
DB_NAME=smart_traffic_lab3_test MINIO_BUCKET=smart-traffic-lab3-test PYTHONPATH=. ../venv/bin/python tests/integration.py
"""
import asyncio
import hashlib
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
import httpx
from main import app
from core.config import ROOT, settings
from core.current_user import get_current_user
from core.storage import get_storage
from db.session import async_session_maker, engine
from models import User, SmartDevice, Like

DEVICE_KEYS = {
    "id", "title", "type_label", "model", "description", "image_key", "video_key",
    "traffic_mean", "traffic_variance", "created_at",
    "formed_at", "creator_id", "is_owner", "liked", "likes_count",
}
checks = 0
async def main():
    global checks
    assert settings.DB_NAME.endswith("_test"), "Use an isolated *_test database"
    assert settings.MINIO_BUCKET.endswith("-test"), "Use an isolated *-test bucket"
    storage = get_storage()
    assert not list(storage.client.list_objects(settings.MINIO_BUCKET)) if storage.client.bucket_exists(settings.MINIO_BUCKET) else True
    async with async_session_maker() as db:
        assert await db.scalar(select(func.count(User.id))) == 0, "Test database must be empty"
        db.add_all([User(username="creator"), User(username="other")])
        await db.flush()
        assert await db.get(User, get_current_user().id) is not None
        own = SmartDevice(title="Xiaomi Existing", description="first", status="published", creator_id=1, traffic_mean=15, traffic_variance=2)
        foreign = SmartDevice(title="Other published", description="second", status="published", creator_id=2, traffic_mean=1, traffic_variance=0.1)
        hidden = SmartDevice(title="Hidden draft", description="hidden", status="draft", creator_id=2)
        deleted = SmartDevice(title="Deleted", description="deleted", status="deleted", creator_id=1)
        db.add_all([own, foreign, hidden, deleted]); await db.commit()
        oid, fid, hid, xid = own.id, foreign.id, hidden.id, deleted.id
    assert get_current_user() is get_current_user()
    image = (ROOT / "static/img/default.jpg").read_bytes()
    video = (ROOT / "static/video/default.mp4").read_bytes()
    data = dict(title="Postman test", description="Description", model="T3", type_label="Camera", traffic_mean="8.5", traffic_variance="1.2")
    def files():
        return {"image": ("картинка.jpg", image, "image/jpeg"), "video": ("видео.mp4", video, "video/mp4")}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        async def call(method, path, status=200, **kw):
            global checks
            response = await client.request(method, path, **kw)
            assert response.status_code in {200, 201, 403, 404}
            assert response.status_code == status, (method, path, response.status_code, response.text)
            if status >= 400:
                assert response.content == b"", (path, response.text)
            if response.content and path.startswith("/api/smart_devices") and "/likes" not in path and status < 400:
                body = response.json()
                for card in body if isinstance(body, list) else [body]:
                    assert set(card) == DEVICE_KEYS, (path, set(card))
            checks += 1
            return response.json() if response.content and response.headers.get("content-type", "").startswith("application/json") else response
        schema = app.openapi()
        assert "status" not in schema["components"]["schemas"]["SmartDeviceOutput"]["properties"]
        assert "content" not in schema["paths"]["/api/smart_devices"]["post"]["responses"]["404"]
        assert sum(len(v) for k,v in schema["paths"].items() if k.startswith('/api')) == 10
        for path in schema["paths"].values():
            for operation in path.values():
                assert set(operation["responses"]) <= {"200", "201", "403", "404"}
        await call("GET", "/api/smart_devices/", 404)
        assert "search" not in {p["name"] for p in schema["paths"]["/api/smart_devices"]["get"].get("parameters", [])}
        assert "image_url" not in SmartDevice.__table__.columns
        assert "video_url" not in SmartDevice.__table__.columns
        cards = await call("GET", "/api/smart_devices")
        assert [d["id"] for d in cards] == [oid, fid]
        assert [d["is_owner"] for d in cards] == [1, 0]
        assert [d["id"] for d in await call("GET", "/api/smart_devices?mean_max=2")] == [fid]
        await call("GET", "/api/smart_devices?mean_max=-1", 404)
        await call("GET", "/api/smart_devices?mean_max=nan", 404)
        await call("GET", "/api/smart_devices/draft", 404)
        # Незаполненный черновик возвращает все те же ключи с null.
        async with async_session_maker() as db:
            partial = SmartDevice(title="Partial", status="draft", creator_id=1)
            db.add(partial); await db.commit(); partial_id = partial.id
        partial_json = await call("GET", "/api/smart_devices/draft")
        assert partial_json["id"] == partial_id
        for field in ["model", "description", "image_key", "video_key", "traffic_mean", "traffic_variance", "formed_at"]:
            assert partial_json[field] is None
        page = await call("GET", "/smart_devices/add")
        assert "Черновик" not in page.text and "draft-badge" not in page.text
        await call("DELETE", f"/api/smart_devices/{partial_id}", 200)
        await call("GET", "/api/smart_devices/draft?id=1", 404)
        await call("GET", "/api/missing", 404)
        await call("PATCH", "/api/smart_devices", 404)
        await call("POST", "/api/users", 404, content="{", headers={"Content-Type": "application/json"})
        assert (await call("GET", "/api/smart_devices/feed"))["id"] == oid
        assert (await call("GET", f"/api/smart_devices/feed?id={oid}&next=true"))["id"] == fid
        assert (await call("GET", f"/api/smart_devices/feed?id={fid}&next=true"))["id"] == oid
        await call("GET", "/api/smart_devices/feed?next=true", 404)
        for device_id in [hid, xid, 999999]:
            await call("GET", f"/api/smart_devices/feed?id={device_id}", 404)
            await call("GET", f"/api/smart_devices/feed?id={device_id}&next=true", 404)
        await call("DELETE", f"/api/smart_devices/{fid}", 403)
        await call("PUT", f"/api/smart_devices/{hid}/publication", 403)
        for key,value in {"id":"100", "status":"published", "creator_id":"2", "moderator_id":"2", "created_at":"2026-01-01", "formed_at":"2026-01-01", "completed_at":"2026-01-01", "image_url":"https://example.org/image.jpg", "image_key":"forged"}.items():
            await call("POST", "/api/smart_devices", 404, data={**data,key:value}, files=files())
        for field,value in [("title","   "),("traffic_mean","-1"),("traffic_variance","nan")]:
            await call("POST", "/api/smart_devices", 404, data={**data,field:value}, files=files())
        await call("POST", "/api/smart_devices", 404, data=data)
        from unittest.mock import patch
        with patch.object(storage, "_put", side_effect=OSError()):
            await call("POST", "/api/smart_devices", 404, data=data, files=files())
        badfiles=files(); badfiles['video']=("fake.mp4", b"not video", "video/mp4")
        await call("POST", "/api/smart_devices", 404, data=data, files=badfiles)
        assert list(storage.client.list_objects(settings.MINIO_BUCKET, recursive=True)) == [], "Image must be cleaned up after video rejection"
        created=await call("POST", "/api/smart_devices", 201, data=data, files=files())
        did=created['id']
        async with async_session_maker() as db:
            assert (await db.get(SmartDevice, did)).status == "draft"
        assert created['creator_id']==1 and created['formed_at'] is None
        for key,expected in [('image_key',image),('video_key',video)]:
            assert created[key].isascii() and 'картинка' not in created[key]
            result=storage.client.get_object(settings.MINIO_BUCKET, created[key])
            try: assert result.read()==expected
            finally: result.close(); result.release_conn()
        async with httpx.AsyncClient() as network:
            from urllib.parse import urlsplit
            for url, content in [(storage.url(created['image_key']), image), (storage.url(created['video_key']), video)]:
                assert not urlsplit(url).query
                downloaded = await network.get(url)
                assert downloaded.status_code == 200 and downloaded.content == content
            assert 'image_url' not in created and 'video_url' not in created
        await call("POST", "/api/smart_devices", 403, data=data, files=files())
        assert (await call("GET", "/api/smart_devices/draft"))['id']==did
        await call("POST", f"/api/smart_devices/{did}/likes", 404, json={'value':1})
        await call("PUT", f"/api/smart_devices/{did}/publication", 404, json={'status':'published'})
        published=await call("PUT", f"/api/smart_devices/{did}/publication", json={})
        async with async_session_maker() as db:
            assert (await db.get(SmartDevice, did)).status == "published"
        assert published['formed_at'] and published['created_at']==created['created_at']
        await call("GET", "/api/smart_devices/draft", 404)
        await call("PUT", f"/api/smart_devices/{did}/publication", 403)
        await call("PUT", f"/api/smart_devices/{did}/publication", 404, json={'status':'draft'})
        for value in [2,-1,True,'1',1.0]:
            await call("POST", f"/api/smart_devices/{did}/likes", 404, json={'value':value})
        await call("POST", f"/api/smart_devices/{did}/likes", 404, json={'value':1,'user_id':2})
        for value,count in [(1,1),(1,1),(0,0),(0,0),(1,1)]:
            result=await call("POST", f"/api/smart_devices/{did}/likes", json={'value':value})
            assert result['liked']==value and result['likes_count']==count
        # Параллельные лайки сериализуются блокировками БД.
        responses=await asyncio.gather(*[client.post(f'/api/smart_devices/{did}/likes',json={'value':1}) for _ in range(4)])
        assert all(r.status_code==200 and r.json()['likes_count']==1 for r in responses)
        for path in ['/smart_devices/feed','/smart_devices/grid','/smart_devices/add','/register']:
            page = await call('GET',path)
            if path.endswith('/grid'): assert 'name="search"' not in page.text
        await call("DELETE", f"/api/smart_devices/{did}", 404, json={'status':'draft'})
        await call("DELETE", f"/api/smart_devices/{did}", 200)
        await call("DELETE", f"/api/smart_devices/{did}", 404)
        await call("GET", f"/api/smart_devices/feed?id={did}", 404)
        await call("POST", f"/api/smart_devices/{did}/likes", 404, json={'value':1})
        assert did not in [d['id'] for d in await call('GET','/api/smart_devices')]
        async with async_session_maker() as db:
            stored=await db.get(SmartDevice,did)
            assert stored.status=='deleted' and stored.completed_at and stored.image_key==created['image_key']
            assert await db.scalar(select(func.count(Like.id)).where(Like.device_id==did))==1
        # Одновременное создание не допускает два черновика.
        responses=await asyncio.gather(*[client.post('/api/smart_devices',data=data,files=files()) for _ in range(2)])
        assert sorted(r.status_code for r in responses)==[201,403]
        draft_id=next(r.json()['id'] for r in responses if r.status_code==201)
        await call('DELETE',f'/api/smart_devices/{draft_id}',200)
        user=await call('POST','/api/users',201,json={'username':'registered','password':'Test password 123'})
        assert 'password' not in user and 'password_hash' not in user
        await call('POST','/api/users',403,json={'username':'registered','password':'Test password 123'})
        await call('POST','/api/users',404,json={'username':'other_new','password':'short'})
        await call('POST','/api/users',404,json={'username':'other_new','password':'long password','id':50})
        async with async_session_maker() as db:
            stored=await db.get(User,user['id'])
            scheme,n,r,p,salt,digest=stored.password_hash.split('$')
            assert scheme=='scrypt' and hashlib.scrypt(b'Test password 123',salt=bytes.fromhex(salt),n=int(n),r=int(r),p=int(p)).hex()==digest
            # Частичный уникальный индекс: два черновика автора 2 запрещены.
            db.add(SmartDevice(title='duplicate',creator_id=2,status='draft'))
            try: await db.commit()
            except IntegrityError: await db.rollback()
            else: raise AssertionError('Draft index missing')
        await call('POST','/api/users/login',200)
        await call('POST','/api/users/logout',200)
    await engine.dispose()
    print(f'PASS: {checks} HTTP checks + fixed card keys/nulls + empty error bodies + PostgreSQL/MinIO + four pages')

if __name__=='__main__':
    asyncio.run(main())
