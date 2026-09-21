from typing import Literal

from pydantic import BaseModel, Field

class ChargerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    room_id: str | None = None
    model: str = "GW7K-HCA-20"
    power_kw: float = Field(default=7, gt=0, le=22)
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
    active_order_id: str | None = None


class PublicCharger(BaseModel):
    code: str
    name: str
    model: str | None = None
    power_kw: float | None = None
    status: str
    telemetry: ChargerSnapshot
    active_session_started_at: str | None = None
    active_session_duration_minutes: int | None = None
    active_session_energy_kwh: float | None = None
    active_order_id: str | None = None
