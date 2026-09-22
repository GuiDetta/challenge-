from typing import Literal

from pydantic import BaseModel


class ChargerAvailability(BaseModel):
    charger_id: str
    name: str
    code: str | None = None
    samples: int
    uptime_percent: float
    charging_percent: float
    fault_percent: float
    offline_percent: float


class AvailabilityReport(BaseModel):
    fleet_uptime_percent: float
    samples: int
    chargers: list[ChargerAvailability]


class FaultItem(BaseModel):
    code: int
    title: str
    severity: Literal["info", "warning", "critical"]
    origin: str
    first_action: str
    escalation: str
    occurrences: int
    chargers: int
    active_alarms: int
    last_seen: str | None = None


class FaultReport(BaseModel):
    total_occurrences: int
    active_alarms: int
    items: list[FaultItem]


class OccupancyHour(BaseModel):
    hour: int
    sessions: int
    energy_kwh: float
    revenue: float


class OccupancyReport(BaseModel):
    total_sessions: int
    peak_hour: int | None = None
    peak_sessions: int
    average_energy_kwh: float
    average_ticket: float
    hours: list[OccupancyHour]


class DemandDay(BaseModel):
    day: str
    peak_kw: float


class DemandReport(BaseModel):
    installed_kw: float
    contracted_kw: float | None = None
    peak_kw: float
    peak_at: str | None = None
    headroom_percent: float | None = None
    daily: list[DemandDay]


class OperationsReport(BaseModel):
    days: int
    generated_at: str
    data_source: Literal["mock", "modbus", "ocpp"] = "mock"
    availability: AvailabilityReport
    faults: FaultReport
    occupancy: OccupancyReport
    demand: DemandReport
