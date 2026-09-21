from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel

from app.schemas import Alarm, Charger, ChargerCreate, ChargerSnapshot, ChargerWithSnapshot, ChargingSession, PublicCharger
from app.services.charger_service import ChargerService
from app.services.container import get_charger_service

router = APIRouter(tags=["chargers"])


class ChargerUpdate(BaseModel):
    name: str | None = None
    x: float | None = None
    y: float | None = None
    room_id: str | None = None


def public_payload(live: dict) -> dict:
    return {key: live.get(key) for key in ("code", "name", "model", "power_kw", "telemetry", "active_session_started_at", "active_session_duration_minutes", "active_session_energy_kwh", "active_order_id")} | {"status": live["telemetry"]["status"]}


@router.get("/api/chargegrid/{code}", response_model=PublicCharger)
def public_charger(code: str, user_id: str | None = Query(default=None), service: ChargerService = Depends(get_charger_service)) -> dict:
    service.database.complete_due_orders()
    charger = service.database.get_charger_by_code(code.upper())
    if charger is None:
        raise HTTPException(status_code=404, detail="Carregador real não encontrado.")
    live = service.with_live_session(charger, user_id) if user_id else {**charger, "telemetry": service.snapshot(charger)}
    return public_payload(live)


@router.get("/api/chargers", response_model=list[ChargerWithSnapshot])
def list_all_real_chargers(owner_id: str, include_inactive: bool = Query(default=False), service: ChargerService = Depends(get_charger_service)) -> list[dict]:
    service.database.complete_due_orders()
    return [service.with_live_session(charger) for charger in service.database.list_real_chargers(owner_id, include_inactive)]


@router.get("/api/plans/{plan_id}/chargers", response_model=list[ChargerWithSnapshot])
def list_chargers(plan_id: str, owner_id: str | None = Query(default=None), include_inactive: bool = Query(default=False), service: ChargerService = Depends(get_charger_service)) -> list[dict]:
    service.plans.get_or_404(plan_id, owner_id)
    service.database.complete_due_orders()
    return [service.with_live_session(charger) for charger in service.database.list_devices(plan_id, "charger", owner_id, include_inactive)]


@router.post("/api/plans/{plan_id}/chargers", response_model=Charger, status_code=201)
def create_charger(plan_id: str, charger_input: ChargerCreate, x_user_id: str | None = Header(default=None), service: ChargerService = Depends(get_charger_service)) -> Charger:
    return service.create(plan_id, charger_input, x_user_id)


@router.patch("/api/plans/{plan_id}/chargers/{charger_id}", response_model=ChargerWithSnapshot)
def update_charger(plan_id: str, charger_id: str, updates: ChargerUpdate, x_user_id: str | None = Header(default=None), service: ChargerService = Depends(get_charger_service)) -> dict:
    return service.update(plan_id, charger_id, updates.model_dump(), x_user_id)


@router.delete("/api/plans/{plan_id}/chargers/{charger_id}", status_code=204)
async def delete_charger(plan_id: str, charger_id: str, request: Request, code: str | None = Query(default=None), payload: dict[str, str] | None = Body(default=None), x_user_id: str | None = Header(default=None), service: ChargerService = Depends(get_charger_service)) -> None:
    request_code = code or (payload or {}).get("code")
    if request_code is None:
        try:
            raw_body = await request.body()
            if raw_body:
                import json
                data = json.loads(raw_body.decode("utf-8", errors="ignore"))
                if isinstance(data, dict):
                    request_code = data.get("code")
        except (json.JSONDecodeError, ValueError):
            pass
    service.delete(plan_id, charger_id, request_code, x_user_id)


@router.get("/api/plans/{plan_id}/chargers/{charger_id}/telemetry", response_model=ChargerSnapshot)
def telemetry(plan_id: str, charger_id: str, service: ChargerService = Depends(get_charger_service)) -> ChargerSnapshot:
    charger = service.get_or_404(plan_id, charger_id)
    return service.snapshot(charger)


@router.get("/api/plans/{plan_id}/chargers/{charger_id}/telemetry/history", response_model=list[ChargerSnapshot])
def telemetry_history(plan_id: str, charger_id: str, limit: int = 50, service: ChargerService = Depends(get_charger_service)) -> list[dict]:
    service.get_or_404(plan_id, charger_id)
    return service.database.list_snapshots(charger_id, max(1, min(limit, 500)))


@router.get("/api/plans/{plan_id}/alarms", response_model=list[Alarm])
def alarms(plan_id: str, active_only: bool = False, service: ChargerService = Depends(get_charger_service)) -> list[dict]:
    service.plans.get_or_404(plan_id)
    return service.database.list_alarms(plan_id, active_only)


@router.get("/api/plans/{plan_id}/sessions", response_model=list[ChargingSession])
def sessions(plan_id: str, service: ChargerService = Depends(get_charger_service)) -> list[dict]:
    service.plans.get_or_404(plan_id)
    return service.database.list_sessions(plan_id)


@router.post("/api/plans/{plan_id}/simulation/tick", response_model=list[ChargerWithSnapshot])
def simulation_tick(plan_id: str, service: ChargerService = Depends(get_charger_service)) -> list[dict]:
    service.plans.get_or_404(plan_id)
    service.database.complete_due_orders()
    return [service.with_live_session(charger) for charger in service.database.list_devices(plan_id, "charger")]
