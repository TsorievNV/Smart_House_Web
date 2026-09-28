from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from core.config import ROOT, settings
from db.session import get_db
from models import SmartDevice, Like, User

router = APIRouter()
templates = Jinja2Templates(directory=ROOT / "templates")
DB = Annotated[AsyncSession, Depends(get_db)]

def devices_query():
    likes = select(func.count(Like.id)).where(Like.device_id == SmartDevice.id).correlate(SmartDevice).scalar_subquery()
    return select(SmartDevice, likes.label("likes_count"))

def card(row):
    device, count = row
    return {**{c.name: getattr(device, c.name) for c in SmartDevice.__table__.columns}, "likes_count": count}

async def current_user(db):
    # Авторизация не входит в ЛР2: демонстрационный пользователь из настроек.
    user = await db.scalar(select(User).where(User.id == settings.CURRENT_USER_ID).with_for_update())
    if user is None:
        raise HTTPException(409, "Сначала импортируйте sql/seed.sql через Adminer")
    return user

@router.get("/feed")
async def feed_page(request: Request, db: DB, id: int | None = None, next: bool = False):
    query = devices_query().where(SmartDevice.status == "published")
    row = None
    if id is not None:
        row = (await db.execute(query.where(SmartDevice.id == id))).first()
        if row is None:
            raise HTTPException(404, "Устройство не найдено или недоступно")
        if next:
            row = (await db.execute(query.where(SmartDevice.id > id).order_by(SmartDevice.id).limit(1))).first()
    if row is None:
        row = (await db.execute(query.order_by(SmartDevice.id).limit(1))).first()
    return templates.TemplateResponse(request=request, name="feed.html",
        context={"device": card(row) if row else None, "active": "feed"})

@router.get("/grid")
async def grid_page(request: Request, db: DB, search: str = "",
                    mean_max: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None):
    query = devices_query().where(SmartDevice.status == "published")
    if search.strip():
        query = query.where(SmartDevice.title.icontains(search.strip(), autoescape=True))
    if mean_max is not None:
        query = query.where(SmartDevice.traffic_mean <= mean_max)
    rows = (await db.execute(query.order_by(SmartDevice.id))).all()
    return templates.TemplateResponse(request=request, name="grid.html", context={
        "cards": [card(row) for row in rows], "search": search, "mean_max": mean_max, "active": "grid"})

@router.get("/add")
async def add_page(request: Request, db: DB):
    device = await db.scalar(select(SmartDevice).where(
        SmartDevice.creator_id == settings.CURRENT_USER_ID, SmartDevice.status == "draft"))
    return templates.TemplateResponse(request=request, name="add.html",
        context={"device": device, "active": "add"})

@router.post("/add")
async def create_device(db: DB, title: Annotated[str, Form(min_length=1, max_length=255)],
                        model: Annotated[str, Form(max_length=100)] = ""):
    title = title.strip()
    if not title:
        raise HTTPException(422, "Укажите название")
    user = await current_user(db)
    device = await db.scalar(select(SmartDevice).where(
        SmartDevice.creator_id == user.id, SmartDevice.status == "draft"))
    if device is None:
        db.add(SmartDevice(title=title, model=model.strip(), status="draft", creator_id=user.id))
        await db.commit()
    return RedirectResponse("/add", status_code=303)

@router.post("/device/{device_id}/publish")
async def publish_device(device_id: int, db: DB,
    title: Annotated[str, Form(min_length=1, max_length=255)],
    description: Annotated[str, Form(min_length=1, max_length=500)],
    traffic_mean: Annotated[float, Form(ge=0, allow_inf_nan=False)],
    traffic_variance: Annotated[float, Form(ge=0, allow_inf_nan=False)],
    model: Annotated[str, Form(max_length=100)] = ""):
    if not title.strip() or not description.strip():
        raise HTTPException(422, "Заполните название и описание")
    device = await db.scalar(select(SmartDevice).where(SmartDevice.id == device_id,
        SmartDevice.creator_id == settings.CURRENT_USER_ID, SmartDevice.status == "draft").with_for_update())
    if device is None:
        raise HTTPException(404, "Черновик не найден")
    device.title, device.description, device.model = title.strip(), description.strip(), model.strip()
    device.traffic_mean, device.traffic_variance = traffic_mean, traffic_variance
    device.status, device.formed_at = "published", datetime.utcnow()
    await db.commit()
    return RedirectResponse(f"/feed?id={device.id}", status_code=303)

@router.post("/device/{device_id}/delete")
async def delete_device(device_id: int, db: DB):
    # Параметризованный SQL UPDATE через драйвер БД, без ORM update/delete.
    cursor = await db.execute(text("""
        UPDATE smart_devices SET status = 'deleted'
        WHERE id = :id AND creator_id = :creator_id AND status <> 'deleted'
        RETURNING id
    """), {"id": device_id, "creator_id": settings.CURRENT_USER_ID})
    if cursor.fetchone() is None:
        raise HTTPException(404, "Устройство не найдено")
    await db.commit()
    return RedirectResponse("/grid", status_code=303)
