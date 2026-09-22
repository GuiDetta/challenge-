from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.schemas import OperationsReport
from app.services import csv_export
from app.services.container import get_order_service, get_report_service
from app.services.order_service import OrderService
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/reports", tags=["reports"])

EXPORTS = {
    "financeiro": ("financial_csv", "financeiro"),
    "disponibilidade": ("availability_csv", "disponibilidade"),
    "falhas": ("faults_csv", "falhas"),
    "erros": ("errors_csv", "log-de-erros"),
}


def as_download(content: str, prefix: str) -> Response:
    name = csv_export.filename(prefix, datetime.now(timezone.utc).isoformat())
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/summary")
def summary(owner_id: str | None = Query(default=None), service: OrderService = Depends(get_order_service)) -> dict:
    return service.database.report_summary(owner_id)


@router.get("/operations", response_model=OperationsReport)
def operations(
    owner_id: str = Query(..., min_length=1),
    days: int = Query(default=7, ge=1, le=90),
    contracted_kw: float | None = Query(default=None, gt=0),
    service: ReportService = Depends(get_report_service),
) -> OperationsReport:
    return service.operations(owner_id, days, contracted_kw)


@router.get("/errors")
def errors(
    owner_id: str = Query(..., min_length=1),
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=50, ge=1, le=500),
    service: ReportService = Depends(get_report_service),
) -> dict:
    return {"events": service.error_log(owner_id, days, limit)}


@router.get("/export/{report}")
def export(
    report: str,
    owner_id: str = Query(..., min_length=1),
    days: int = Query(default=30, ge=1, le=365),
    service: ReportService = Depends(get_report_service),
) -> Response:
    if report not in EXPORTS:
        raise HTTPException(status_code=404, detail=f"Relatório desconhecido. Use um destes: {', '.join(EXPORTS)}.")
    method, prefix = EXPORTS[report]
    return as_download(getattr(service, method)(owner_id, days), prefix)
