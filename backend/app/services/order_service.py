from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException

from app.repositories import Database, InsufficientBalanceError
from app.schemas import ChargingOrderCreate, ChargingOrderFinish, WalletTopUp


PEAK_START_HOUR = 18
PEAK_END_HOUR = 22
PEAK_PRICE_PER_KWH = 2.79
OFF_PEAK_PRICE_PER_KWH = 1.99


def current_tariff(now: datetime | None = None) -> dict:
    now = now or datetime.now().astimezone()
    is_peak = PEAK_START_HOUR <= now.hour < PEAK_END_HOUR
    if is_peak:
        next_change = now.replace(hour=PEAK_END_HOUR, minute=0, second=0, microsecond=0)
    else:
        next_change = now.replace(hour=PEAK_START_HOUR, minute=0, second=0, microsecond=0)
        if now.hour >= PEAK_END_HOUR:
            next_change += timedelta(days=1)
    return {
        "price_per_kwh": PEAK_PRICE_PER_KWH if is_peak else OFF_PEAK_PRICE_PER_KWH,
        "is_peak": is_peak,
        "peak_window": f"{PEAK_START_HOUR}h às {PEAK_END_HOUR}h",
        "peak_price_per_kwh": PEAK_PRICE_PER_KWH,
        "off_peak_price_per_kwh": OFF_PEAK_PRICE_PER_KWH,
        "next_change_at": next_change.isoformat(),
    }


class OrderService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, order_input: ChargingOrderCreate) -> dict:
        if self.database.get_user(order_input.user_id) is None:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        charger = self.database.get_charger_by_code(order_input.charger_code.upper())
        if charger is None:
            raise HTTPException(status_code=404, detail="Carregador real não encontrado.")
        now = datetime.now().astimezone()
        price_per_kwh = current_tariff(now)["price_per_kwh"]
        estimated_duration_minutes = max(1, round(order_input.energy_kwh / float(charger["power_kw"] or 7) * 60))
        order = {"id": str(uuid4()), **order_input.model_dump(), "charger_code": order_input.charger_code.upper(), "price_per_kwh": price_per_kwh, "scheduled_at": now.isoformat(), "estimated_duration_minutes": estimated_duration_minutes, "total_amount": round(order_input.energy_kwh * price_per_kwh, 2)}
        try:
            created_order = self.database.create_order(order)
        except InsufficientBalanceError as error:
            raise HTTPException(status_code=402, detail="Saldo insuficiente para iniciar esta recarga.") from error
        self.database.activate_charger_by_code(order_input.charger_code.upper())
        return created_order

    def finish(self, order_id: str, finish_input: ChargingOrderFinish) -> dict:
        try:
            result = self.database.finish_order(order_id, finish_input.user_id, finish_input.energy_delivered_kwh)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        self.database.complete_due_orders()
        return result

    def top_up(self, top_up: WalletTopUp) -> dict:
        if self.database.get_user(top_up.user_id) is None:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        return self.database.add_wallet_transaction({"id": str(uuid4()), "user_id": top_up.user_id, "amount": top_up.amount, "type": "top_up", "method": top_up.method})

    def wallet(self, user_id: str) -> dict:
        if self.database.get_user(user_id) is None:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        return self.database.wallet_statement(user_id)

    def list_for_user(self, user_id: str) -> list[dict]:
        if self.database.get_user(user_id) is None:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        self.database.complete_due_orders()
        return self.database.list_user_orders(user_id)
