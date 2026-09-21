from typing import Literal

from pydantic import BaseModel


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
