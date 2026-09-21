from fastapi import APIRouter, Depends, Query

from app.services.container import get_order_service
from app.services.order_service import OrderService

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/summary")
def summary(owner_id: str | None = Query(default=None), service: OrderService = Depends(get_order_service)) -> dict:
    return service.database.report_summary(owner_id)
