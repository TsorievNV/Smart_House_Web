from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from data.collections import MINIO_BASE, smart_devices

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_media_url(key: str) -> str:
    if not key:
        return "/static/img/default.jpg"

    return f"{MINIO_BASE}/{quote(key)}"


def published_devices():
    return [device for device in smart_devices if device["status"] == "published"]


def get_device_by_id(device_id: int):
    return next(
        (device for device in smart_devices if device["id"] == device_id),
        None,
    )


def enrich(device: dict) -> dict:
    result = device.copy()
    result["image_url"] = get_media_url(result.get("image_key", ""))
    video_key = result.get("video_key", "")
    result["video_url"] = get_media_url(video_key) if video_key else ""
    result["likes_count"] = len(result.get("likes", []))
    return result


@router.get(
    "/.well-known/appspecific/com.chrome.devtools.json",
    include_in_schema=False,
)
def chrome_devtools_config():
    return Response(status_code=204)


@router.get("/")
def root():
    return RedirectResponse(url="/feed")


@router.get("/feed")
def feed_page(
    request: Request,
    id: Optional[int] = None,
    next: Optional[bool] = False,
):
    pubs = published_devices()

    if not pubs:
        return templates.TemplateResponse(
            request=request,
            name="feed.html",
            context={
                "device": None,
                "active": "feed",
            },
        )

    if id is None:
        device = pubs[0]
    else:
        current = get_device_by_id(id)

        if current is None or current["status"] != "published":
            device = pubs[0]
        elif next:
            ids = [item["id"] for item in pubs]

            try:
                idx = ids.index(id)
                device = pubs[(idx + 1) % len(ids)]
            except ValueError:
                device = pubs[0]
        else:
            device = current

    return templates.TemplateResponse(
        request=request,
        name="feed.html",
        context={
            "device": enrich(device),
            "active": "feed",
        },
    )


@router.get("/add")
def add_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="add.html",
        context={"active": "add"},
    )


@router.get("/grid")
def grid_page(
    request: Request,
    mean_max: Optional[float] = Query(None),
):
    pubs = published_devices()

    if mean_max is not None:
        pubs = [
            device
            for device in pubs
            if device["traffic_mean"] <= mean_max
        ]

    cards = [enrich(device) for device in pubs]

    return templates.TemplateResponse(
        request=request,
        name="grid.html",
        context={
            "cards": cards,
            "mean_max": mean_max,
            "active": "grid",
        },
    )
