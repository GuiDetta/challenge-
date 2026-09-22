from app.core.dependencies import get_database, get_plan_processor, get_store
from app.services.assistant_service import AssistantService
from app.services.auth_service import AuthService
from app.services.charger_service import ChargerService
from app.services.order_service import OrderService
from app.services.plan_service import PlanService
from app.services.report_service import ReportService


def get_plan_service() -> PlanService:
    return PlanService(get_database(), get_store(), get_plan_processor())


def get_charger_service() -> ChargerService:
    return ChargerService(get_database(), get_plan_service())


def get_auth_service() -> AuthService:
    return AuthService(get_database())


def get_order_service() -> OrderService:
    return OrderService(get_database())


def get_report_service() -> ReportService:
    return ReportService(get_database())


def get_assistant_service() -> AssistantService:
    return AssistantService(get_database(), get_charger_service())
