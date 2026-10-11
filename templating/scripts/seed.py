"""Идемпотентное заполнение через ORM. python -m scripts.seed"""
import asyncio
from io import BytesIO
from sqlalchemy import select, func
from starlette.datastructures import UploadFile, Headers
from core.config import ROOT
from core.current_user import get_current_user
from core.storage import get_storage
from data.smart_devices import smart_devices
from db.session import async_session_maker, engine
from models import User, SmartDevice
from datetime import datetime

async def main():
    storage = get_storage()
    async with async_session_maker() as db:
        user_id = get_current_user().id
        if await db.get(User, user_id) is None:
            db.add(User(id=user_id, username="lab3_creator"))
            await db.flush()
        # Явный ID singleton требует синхронизировать sequence PostgreSQL.
        maximum = await db.scalar(select(func.max(User.id)))
        await db.execute(select(func.setval(func.pg_get_serial_sequence("users", "id"), maximum, True)))
        await db.commit()
        for source in smart_devices[:7]:
            if await db.scalar(select(SmartDevice.id).where(SmartDevice.title == source["title"])):
                continue
            keys = []
            try:
                for kind, path, mime in [("image", ROOT / "static/img/default.jpg", "image/jpeg"),
                                         ("video", ROOT / "static/video/default.mp4", "video/mp4")]:
                    data = path.read_bytes()
                    upload = UploadFile(BytesIO(data), size=len(data), filename=path.name, headers=Headers({"content-type": mime}))
                    try:
                        keys.append(await storage.save(upload, kind))
                    finally:
                        await upload.close()
                db.add(SmartDevice(title=source["title"], type_label=source["type_label"],
                    description=source["description"], traffic_mean=source["traffic_mean"],
                    traffic_variance=source["traffic_variance"], creator_id=user_id,
                    status="published", formed_at=datetime.utcnow(), image_key=keys[0], video_key=keys[1]))
                await db.commit()
            except Exception:
                await db.rollback()
                for key in keys:
                    await storage.remove(key)
                raise
    await engine.dispose()
    print("Демо-пользователь и 7 карточек готовы. Медиа — демонстрационные заглушки в MinIO.")

if __name__ == "__main__":
    asyncio.run(main())
