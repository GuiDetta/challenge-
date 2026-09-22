from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from app.schemas.auth import UserCreate, UserLogin
from app.schemas.charger import Charger, ChargerCreate, ChargerSnapshot, ChargerWithSnapshot, PublicCharger
from app.schemas.device import Device, DeviceCreate
from app.schemas.order import ChargingOrderCreate, ChargingOrderFinish, WalletTopUp
from app.schemas.plan import PlanMap
from app.schemas.report import (
    AvailabilityReport,
    ChargerAvailability,
    DemandDay,
    DemandReport,
    FaultItem,
    FaultReport,
    OccupancyHour,
    OccupancyReport,
    OperationsReport,
)
from app.schemas.session import Alarm, ChargingSession

__all__ = [
    "Alarm",
    "AssistantChatRequest",
    "AssistantChatResponse",
    "AvailabilityReport",
    "Charger",
    "ChargerAvailability",
    "ChargerCreate",
    "ChargerSnapshot",
    "ChargerWithSnapshot",
    "ChargingOrderCreate",
    "ChargingOrderFinish",
    "ChargingSession",
    "DemandDay",
    "DemandReport",
    "Device",
    "DeviceCreate",
    "FaultItem",
    "FaultReport",
    "OccupancyHour",
    "OccupancyReport",
    "OperationsReport",
    "PlanMap",
    "PublicCharger",
    "UserCreate",
    "UserLogin",
    "WalletTopUp",
]
