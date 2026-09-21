from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException

from app.repositories import Database, InsufficientBalanceError
from app.schemas import ChargingOrderCreate, ChargingOrderFinish, WalletTopUp


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
        is_peak = 18 <= now.hour < 22
        price_per_kwh = 2.79 if is_peak else 1.99
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
        return self.database.add_wallet_transaction({"id": str(uuid4()), "user_id": top_up.user_id, "amount": top_up.amount, "type": "top_up"})
