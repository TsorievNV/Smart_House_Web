"""Run against a migrated, isolated PostgreSQL test database. Never production."""
import asyncio
from pathlib import Path
import httpx
from sqlalchemy import select, text
from main import app
from db.session import async_session_maker, engine
from models import SmartDevice
from data.collections import smart_devices

async def main():
    from core.config import settings
    assert settings.DB_NAME.endswith("_test"), "Use an isolated *_test database"
    async with async_session_maker() as db:
        # Fixture import; deployment data must be imported through Adminer.
        raw = await db.connection()
        driver = (await raw.get_raw_connection()).driver_connection
        await driver.execute(Path('sql/seed.sql').read_text())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as c:
        paths=app.openapi()['paths']
        assert sum(len([m for m in p if m in ('get','post')]) for p in paths.values()) == 6
        grid=await c.get('/grid'); assert grid.status_code==200
        for d in smart_devices[:7]: assert d['title'] in grid.text
        assert 'Удалённое устройство' not in grid.text
        assert (await c.get('/feed?id=8')).status_code==404
        assert (await c.get('/feed?id=8&next=true')).status_code==404
        assert (await c.get('/feed?id=9')).status_code==404
        assert (await c.get('/feed?id=99999')).status_code==404
        assert 'Roborock S8' in (await c.get('/grid?search=roborock')).text
        assert 'Xiaomi Smart Camera' not in (await c.get('/grid?search=roborock')).text
        assert 'Samsung Smart TV' not in (await c.get('/grid?mean_max=1')).text
        assert 'Далее' in (await c.get('/add')).text
        async with async_session_maker() as db:
            assert await db.scalar(select(SmartDevice.id).where(SmartDevice.creator_id==1, SmartDevice.status=='draft')) is None
        for _ in range(2):
            assert (await c.post('/add',data={'title':'Тестовая карточка','model':'T1'})).status_code==303
        async with async_session_maker() as db:
            draft=(await db.scalars(select(SmartDevice).where(SmartDevice.creator_id==1,SmartDevice.status=='draft'))).one()
            did=draft.id
            assert draft.image_url is None and draft.video_url is None
        assert 'Опубликовать' in (await c.get('/add')).text
        data={'title':'Тестовая карточка','description':'Описание теста','traffic_mean':'2.5','traffic_variance':'0.4','model':'T1'}
        assert (await c.post(f'/device/{did}/publish',data={**data,'traffic_mean':'-1'})).status_code==422
        assert (await c.post(f'/device/{did}/publish',data=data)).status_code==303
        assert (await c.post(f'/device/{did}/publish',data=data)).status_code==404
        async with async_session_maker() as db:
            draft=await db.get(SmartDevice,did)
            assert draft.formed_at and draft.status=='published'
            await db.execute(text('UPDATE smart_devices SET traffic_mean=7.75 WHERE id=:id'),{'id':did})
            await db.execute(text('INSERT INTO likes(user_id,device_id) VALUES(2,:id)'),{'id':did})
            await db.commit()
        feed=await c.get(f'/feed?id={did}')
        assert '7.75' in feed.text and '<span class="like-count">1</span>' in feed.text
        assert '/static/video/default.mp4' in feed.text
        assert (await c.post(f'/device/{did}/delete')).status_code==303
        assert (await c.get(f'/feed?id={did}')).status_code==404
        async with async_session_maker() as db:
            assert (await db.get(SmartDevice,did)).status=='deleted'
            assert await db.scalar(text('SELECT count(*) FROM likes WHERE device_id=:id'),{'id':did})==1
            # A second draft and a physical deletion with references must fail.
            for sql in ["INSERT INTO smart_devices(title,status,creator_id,created_at) VALUES('duplicate','draft',7,NOW())",'DELETE FROM smart_devices WHERE id=1']:
                try:
                    await db.execute(text(sql))
                except Exception:
                    await db.rollback()
                else:
                    raise AssertionError('DB invariant missing')
        assert (await c.get('/static/video/default.mp4')).status_code==200
    await engine.dispose()
    print('PASS: six controllers, seven cards, search/filter, drafts, publication, SQL deletion, DB changes/likes, invariants, media')

if __name__=='__main__':
    asyncio.run(main())
