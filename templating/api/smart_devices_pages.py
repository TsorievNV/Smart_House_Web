"""Четыре страницы используют ту же логику чтения, что JSON API."""
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.templating import Jinja2Templates
from typing import Annotated
from core.config import ROOT
from api.smart_devices import DB, Current, OptionalCurrent, Storage, list_smart_devices, feed, draft

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=ROOT / "templates")

@router.get("/smart_devices/grid")
async def grid_page(request: Request, db: DB, current: OptionalCurrent, storage: Storage,
    mean_max: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None):
    return templates.TemplateResponse(request=request, name="smart_devices_grid.html", context={
        "cards": await list_smart_devices(db, current, storage, mean_max),
        "mean_max": mean_max, "active": "grid", "media_url": storage.url})

@router.get("/smart_devices/feed")
async def feed_page(request: Request, db: DB, current: OptionalCurrent, storage: Storage,
                    id: Annotated[int | None, Query(gt=0)] = None, next: bool = False):
    try:
        device = await feed(db, current, storage, id, next)
    except HTTPException as exc:
        if exc.status_code != 404 or id is not None:
            raise
        device = None
    return templates.TemplateResponse(request=request, name="smart_devices_feed.html", context={
        "device": device, "active": "feed", "media_url": storage.url})

@router.get("/smart_devices/add")
async def add_page(request: Request, db: DB, current: Current, storage: Storage):
    try:
        device = await draft(db, current, storage)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        device = None
    return templates.TemplateResponse(request=request, name="smart_devices_add.html", context={
        "device": device, "active": "add", "media_url": storage.url})

@router.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="users_register.html", context={"active": "register"})
