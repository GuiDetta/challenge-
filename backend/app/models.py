from typing import Literal

from pydantic import BaseModel, Field


class Point(BaseModel):
    x: float
    y: float


class Room(BaseModel):
    id: str
    name: str
    polygon: list[Point]
    bounds: dict[str, float]
    area: float


class Wall(BaseModel):
    id: str
    points: list[Point]


class TextRegion(BaseModel):
    text: str
    bounds: dict[str, float]
    confidence: float | None = None


class PlanMap(BaseModel):
    plan_id: str
    width: int
    height: int
    rooms: list[Room]
    walls: list[Wall]
    texts: list[TextRegion]
    svg: str
    ocr_available: bool
    warnings: list[str] = Field(default_factory=list)


class ChargerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    room_id: str | None = None
    model: str = "GW11K-HCA-20"
    power_kw: float = Field(default=11, gt=0, le=22)
    phase: Literal["single", "three"] = "three"
    rated_current_a: float | None = Field(default=None, gt=0)
    metadata: dict[str, str] = Field(default_factory=dict)


class Charger(ChargerCreate):
    id: str
    plan_id: str
    device_type: Literal["charger"] = "charger"


class ChargerSnapshot(BaseModel):
    status: Literal["available", "preparing", "charging", "suspended", "finished", "faulted", "offline"]
    connection_status: Literal["connected", "disconnected"]
    power_kw: float
    voltage_v: float
    current_a: float
    energy_kwh: float
    session_energy_kwh: float
    temperature_c: float
    fault_code: int
    alarm_code: int
    source: Literal["mock", "modbus", "ocpp"]
    recorded_at: str
    fault_description: str | None = None


class ChargerWithSnapshot(Charger):
    telemetry: ChargerSnapshot


class Alarm(BaseModel):
    id: str
    charger_id: str
    code: int
    severity: Literal["info", "warning", "critical"]
    title: str
    detail: str
    active: bool
    created_at: str
    cleared_at: str | None = None


class ChargingSession(BaseModel):
    id: str
    charger_id: str
    started_at: str
    ended_at: str | None = None
    status: Literal["active", "completed", "interrupted"]
    energy_kwh: float
    duration_seconds: int
    start_meter_kwh: float | None = None
    end_meter_kwh: float | None = None
    start_mode: str | None = None
    end_reason: str | None = None


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
