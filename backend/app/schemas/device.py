from typing import Literal

from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    device_type: Literal["charger", "sensor", "camera", "other"] = "charger"
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    room_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class Device(DeviceCreate):
    id: str
    plan_id: str
