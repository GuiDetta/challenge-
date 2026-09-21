from fastapi import APIRouter, Depends

from app.schemas import ChargingOrderCreate, ChargingOrderFinish, WalletTopUp
from app.services.container import get_order_service
from app.services.order_service import OrderService

router = APIRouter(tags=["orders"])


@router.post("/api/charging-orders", status_code=201)
def create_order(order_input: ChargingOrderCreate, service: OrderService = Depends(get_order_service)) -> dict:
    return service.create(order_input)


@router.post("/api/charging-orders/{order_id}/finish")
def finish_order(order_id: str, finish_input: ChargingOrderFinish, service: OrderService = Depends(get_order_service)) -> dict:
    return service.finish(order_id, finish_input)


@router.post("/api/wallet/top-ups", status_code=201)
def top_up(top_up: WalletTopUp, service: OrderService = Depends(get_order_service)) -> dict:
    return service.top_up(top_up)
