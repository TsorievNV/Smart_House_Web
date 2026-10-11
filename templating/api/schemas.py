"""Сериализаторы входа и выхода. Системные поля не входят во входные модели."""
from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt

class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class SmartDeviceInput(InputModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=500)
    model: str = Field(default="", max_length=100)
    type_label: str = Field(default="УМНОЕ УСТРОЙСТВО", min_length=1, max_length=100)
    traffic_mean: float = Field(ge=0, allow_inf_nan=False)
    traffic_variance: float = Field(ge=0, allow_inf_nan=False)

class EmptyInput(InputModel):
    pass

class LikeInput(InputModel):
    value: Annotated[StrictInt, Field(ge=0, le=1)]

class LikeOutput(BaseModel):
    device_id: int
    is_liked: Literal[0, 1]
    likes_count: int

class UserInput(InputModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    username: str = Field(min_length=3, max_length=100, pattern=r"^[\w.-]+$")
    password: str = Field(min_length=8, max_length=128)

class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    created_at: datetime

class SmartDeviceOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    type_label: str
    model: str | None
    description: str | None
    image_key: str | None
    video_key: str | None
    traffic_mean: float | None
    traffic_variance: float | None
    created_at: datetime
    formed_at: datetime | None
    creator_id: int
    is_owner: Literal[0, 1] = 0
    is_liked: Literal[0, 1] = 0
    likes_count: int = 0

