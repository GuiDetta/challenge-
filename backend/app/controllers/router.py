from fastapi import APIRouter

from app.controllers.assistant_controller import router as assistant_router
from app.controllers.auth_controller import router as auth_router
from app.controllers.charger_controller import router as charger_router
from app.controllers.health_controller import router as health_router
from app.controllers.order_controller import router as order_router
from app.controllers.plan_controller import router as plan_router
from app.controllers.report_controller import router as report_router

api_router = APIRouter()
for router in (health_router, assistant_router, auth_router, order_router, plan_router, charger_router, report_router):
    api_router.include_router(router)
