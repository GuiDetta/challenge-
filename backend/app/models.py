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
    kind: Literal["real", "simulated"] = "simulated"
    code: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    owner_id: str | None = None
    active: bool = True


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
    active_session_started_at: str | None = None
    active_session_duration_minutes: int | None = None
    active_session_energy_kwh: float | None = None


class PublicCharger(BaseModel):
    code: str
    name: str
    model: str | None = None
    power_kw: float | None = None
    status: str
    telemetry: ChargerSnapshot


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    password: str = Field(min_length=6, max_length=128)
    role: Literal["cliente", "lojista", "instalador"] = "cliente"


class UserLogin(BaseModel):
    email: str = Field(min_length=5, max_length=180)
    password: str = Field(min_length=1, max_length=128)


class ChargingOrderCreate(BaseModel):
    user_id: str
    charger_code: str
    energy_kwh: float = Field(gt=0, le=500)
    payment_method: Literal["pix", "paypal", "wallet"]


class WalletTopUp(BaseModel):
    user_id: str
    amount: Literal[10, 25, 50, 100]


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AssistantChatRequest(BaseModel):
    owner_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=4000)
    history: list[AssistantMessage] = Field(default_factory=list, max_length=20)


class AssistantChatResponse(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str
    system_alerts: list[str] = Field(default_factory=list)
    provider: Literal["openai", "local"]


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
