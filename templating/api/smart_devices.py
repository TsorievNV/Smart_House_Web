"""REST-домен устройств: только ORM, явные переходы состояний."""
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from api.schemas import SmartDeviceInput, SmartDeviceOutput, EmptyInput, LikeInput, LikeOutput
from core.current_user import CurrentUser, get_current_user
from core.storage import MediaStorage, get_storage
from db.session import get_db
from models import SmartDevice, Like, User

router = APIRouter(prefix="/api/smart_devices", tags=["Устройства"])
DB = Annotated[AsyncSession, Depends(get_db)]
Current = Annotated[CurrentUser, Depends(get_current_user)]
Storage = Annotated[MediaStorage, Depends(get_storage)]

async def reject_query(request: Request):
    if request.query_params:
        raise HTTPException(404)

async def reject_body(request: Request):
    if await request.body():
        raise HTTPException(404)

async def smart_device_fields(request: Request,
    title: Annotated[str, Form()], description: Annotated[str, Form()],
    traffic_mean: Annotated[float, Form()], traffic_variance: Annotated[float, Form()],
    model: Annotated[str, Form()] = "", type_label: Annotated[str, Form()] = "УМНОЕ УСТРОЙСТВО") -> SmartDeviceInput:
    form = await request.form()
    allowed = set(SmartDeviceInput.model_fields) | {"image", "video"}
    if set(form) - allowed or any(len(form.getlist(k)) != 1 for k in form):
        raise HTTPException(404)
    try:
        return SmartDeviceInput(title=title, description=description, model=model, type_label=type_label,
                           traffic_mean=traffic_mean, traffic_variance=traffic_variance)
    except ValidationError as exc:
        # Внутренние данные валидации; клиент получает только HTTP-код.
        errors = exc.errors(include_input=False, include_url=False)
        for error in errors:
            error["loc"] = ("body", *error["loc"])
        raise RequestValidationError(errors) from exc

async def lock_user(db, current):
    user = await db.scalar(select(User).where(User.id == current.id).with_for_update())
    if user is None:
        raise HTTPException(404)
    return user

def smart_devices_query(current):
    likes = select(func.count(Like.id)).where(Like.device_id == SmartDevice.id).correlate(SmartDevice).scalar_subquery()
    is_liked = select(Like.id).where(Like.device_id == SmartDevice.id, Like.user_id == current.id).correlate(SmartDevice).exists()
    return select(SmartDevice, likes.label("likes_count"), is_liked.label("is_liked"))

def serialize(row, current):
    device, count, is_liked = row
    return SmartDeviceOutput.model_validate(device).model_copy(update={
        "likes_count": count, "is_liked": int(is_liked), "is_owner": int(device.creator_id == current.id),
    })

async def read_smart_device(db, device_id, current, storage):
    row = (await db.execute(smart_devices_query(current).where(SmartDevice.id == device_id,
                            SmartDevice.status != "deleted"))).one()
    return serialize(row, current)

@router.get("", response_model=list[SmartDeviceOutput])
async def list_smart_devices(db: DB, current: Current, storage: Storage,
    mean_max: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None):
    query = smart_devices_query(current).where(SmartDevice.status == "published")
    if mean_max is not None:
        query = query.where(SmartDevice.traffic_mean <= mean_max)
    return [serialize(row, current) for row in (await db.execute(query.order_by(SmartDevice.id))).all()]

@router.get("/feed", response_model=SmartDeviceOutput)
async def feed(db: DB, current: Current, storage: Storage,
               id: Annotated[int | None, Query(gt=0)] = None, next: bool = False):
    if next and id is None:
        raise HTTPException(404)
    query = smart_devices_query(current).where(SmartDevice.status == "published")
    row = None
    if id is not None:
        row = (await db.execute(query.where(SmartDevice.id == id))).first()
        if row is None:
            raise HTTPException(404)
        if next:
            row = (await db.execute(query.where(SmartDevice.id > id).order_by(SmartDevice.id).limit(1))).first()
    if row is None:
        row = (await db.execute(query.order_by(SmartDevice.id).limit(1))).first()
    if row is None:
        raise HTTPException(404)
    return serialize(row, current)

@router.get("/draft", response_model=SmartDeviceOutput, dependencies=[Depends(reject_query)])
async def draft(db: DB, current: Current, storage: Storage):
    row = (await db.execute(smart_devices_query(current).where(SmartDevice.creator_id == current.id,
                                                       SmartDevice.status == "draft"))).first()
    if row is None:
        raise HTTPException(404)
    return serialize(row, current)

@router.post("", response_model=SmartDeviceOutput, status_code=201, dependencies=[Depends(reject_query)])
async def create_smart_device(db: DB, current: Current, storage: Storage,
    fields: Annotated[SmartDeviceInput, Depends(smart_device_fields)],
    image: Annotated[UploadFile, File()], video: Annotated[UploadFile, File()]):
    await lock_user(db, current)
    if await db.scalar(select(SmartDevice.id).where(SmartDevice.creator_id == current.id, SmartDevice.status == "draft")):
        raise HTTPException(403)
    keys = []
    try:
        keys.append(await storage.save(image, "image"))
        keys.append(await storage.save(video, "video"))
        device = SmartDevice(**fields.model_dump(), creator_id=current.id, status="draft",
                             image_key=keys[0], video_key=keys[1])
        db.add(device)
        await db.flush()
        result = await read_smart_device(db, device.id, current, storage)
        await db.commit()
        return result
    except Exception as exc:
        await db.rollback()
        for key in keys:
            await storage.remove(key)
        if isinstance(exc, IntegrityError):
            raise HTTPException(403) from exc
        raise
    finally:
        await image.close()
        await video.close()

async def owned_smart_device(db, device_id, current):
    device = await db.scalar(select(SmartDevice).where(SmartDevice.id == device_id,
        SmartDevice.status != "deleted").with_for_update())
    if device is None:
        raise HTTPException(404)
    if device.creator_id != current.id:
        raise HTTPException(403)
    return device

@router.put("/{device_id}/publication", response_model=SmartDeviceOutput, dependencies=[Depends(reject_query)])
async def publish_smart_device(device_id: int, db: DB, current: Current, storage: Storage,
                         payload: Annotated[EmptyInput, Body()] = EmptyInput()):
    device = await owned_smart_device(db, device_id, current)
    if device.status != "draft":
        raise HTTPException(403)
    if not device.title or not device.description or device.traffic_mean is None or device.traffic_variance is None:
        raise HTTPException(403)
    if not device.image_key or not device.video_key:
        raise HTTPException(403)
    device.status, device.formed_at = "published", datetime.utcnow()
    await db.flush()
    result = await read_smart_device(db, device.id, current, storage)
    await db.commit()
    return result

@router.delete("/{device_id}", status_code=200, response_class=Response, dependencies=[Depends(reject_query), Depends(reject_body)])
async def delete_smart_device(device_id: int, db: DB, current: Current):
    device = await owned_smart_device(db, device_id, current)
    device.status, device.completed_at = "deleted", datetime.utcnow()
    await db.commit()
    return Response(status_code=200)

@router.post("/{device_id}/likes", response_model=LikeOutput, dependencies=[Depends(reject_query)])
async def set_like(device_id: int, payload: LikeInput, db: DB, current: Current):
    await lock_user(db, current)
    device = await db.scalar(select(SmartDevice).where(SmartDevice.id == device_id,
        SmartDevice.status == "published").with_for_update())
    if device is None:
        raise HTTPException(404)
    like = await db.scalar(select(Like).where(Like.device_id == device_id, Like.user_id == current.id))
    if payload.value == 1 and like is None:
        db.add(Like(device_id=device_id, user_id=current.id))
    elif payload.value == 0 and like is not None:
        await db.delete(like)
    await db.flush()
    count = await db.scalar(select(func.count(Like.id)).where(Like.device_id == device_id))
    await db.commit()
    return LikeOutput(device_id=device_id, is_liked=payload.value, likes_count=count)
