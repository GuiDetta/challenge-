from fastapi import APIRouter, Depends, File, Header, UploadFile

from app.schemas import Device, DeviceCreate, PlanMap
from app.services.container import get_plan_service
from app.services.plan_service import PlanService

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.post("", response_model=PlanMap, status_code=201)
async def upload_plan(file: UploadFile = File(...), x_user_id: str | None = Header(default=None), service: PlanService = Depends(get_plan_service)) -> PlanMap:
    return await service.upload(file, x_user_id)


@router.get("", response_model=list[PlanMap])
def list_plans(owner_id: str, service: PlanService = Depends(get_plan_service)) -> list[dict]:
    return service.database.list_plans_for_owner(owner_id)


@router.get("/{plan_id}", response_model=PlanMap)
def get_plan(plan_id: str, owner_id: str | None = None, service: PlanService = Depends(get_plan_service)) -> dict:
    return service.get_or_404(plan_id, owner_id)


@router.get("/{plan_id}/devices", response_model=list[Device])
def list_devices(plan_id: str, service: PlanService = Depends(get_plan_service)) -> list[dict]:
    service.get_or_404(plan_id)
    return service.database.list_devices(plan_id)


@router.post("/{plan_id}/devices", response_model=Device, status_code=201)
def add_device(plan_id: str, device_input: DeviceCreate, service: PlanService = Depends(get_plan_service)) -> Device:
    return service.add_device(plan_id, device_input)


@router.delete("/{plan_id}/devices/{device_id}", status_code=204)
def delete_device(plan_id: str, device_id: str, service: PlanService = Depends(get_plan_service)) -> None:
    service.delete_device(plan_id, device_id)
