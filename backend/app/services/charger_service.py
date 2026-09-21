import json
from uuid import uuid4

from fastapi import HTTPException

from app.repositories import Database
from app.schemas import Charger, ChargerCreate
from app.services.charger_simulator import FAULTS, snapshot_for
from app.services.plan_service import PlanService


class ChargerService:
    def __init__(self, database: Database, plans: PlanService) -> None:
        self.database = database
        self.plans = plans

    def get_or_404(self, plan_id: str, charger_id: str, owner_id: str | None = None) -> dict:
        self.plans.get_or_404(plan_id, owner_id)
        charger = self.database.get_device(charger_id)
        if charger is None or charger["plan_id"] != plan_id or charger["device_type"] != "charger" or (owner_id and charger.get("owner_id") != owner_id):
            raise HTTPException(status_code=404, detail="Carregador não encontrado.")
        return charger

    def snapshot(self, charger: dict) -> dict:
        snapshot = snapshot_for(charger)
        self.database.save_snapshot(charger["id"], snapshot)
        if snapshot["fault_code"]:
            self.database.save_alarm({"id": f"{charger['id']}-{snapshot['fault_code']}", "charger_id": charger["id"], "code": snapshot["fault_code"], "severity": "critical", "title": FAULTS.get(snapshot["fault_code"], "Falha do carregador"), "detail": snapshot.get("fault_description") or "Falha simulada pelo monitoramento.", "active": True, "created_at": snapshot["recorded_at"]})
        return snapshot

    def with_live_session(self, charger: dict, user_id: str | None = None) -> dict:
        session = self.database.get_active_order_for_charger(charger["code"], user_id)
        telemetry = self.snapshot(charger)
        if session:
            return {**charger, "telemetry": telemetry, "active_session_started_at": session["created_at"], "active_session_duration_minutes": session["estimated_duration_minutes"], "active_session_energy_kwh": session["energy_kwh"], "active_order_id": session["id"]}
        return {**charger, "telemetry": telemetry}

    def create(self, plan_id: str, charger_input: ChargerCreate, owner_id: str | None) -> Charger:
        plan = self.plans.get_or_404(plan_id, owner_id)
        if charger_input.x > plan["width"] or charger_input.y > plan["height"]:
            raise HTTPException(status_code=422, detail="A posição do carregador está fora dos limites da planta.")
        payload = charger_input.model_dump()
        payload["owner_id"] = owner_id or payload.get("owner_id")
        code = payload.get("code") or Database.generate_device_code()
        payload["code"] = code
        payload["metadata"] = {**charger_input.metadata, "kind": charger_input.kind, "code": code, "payment_active": "false" if charger_input.kind == "real" else "true"}
        charger = Charger(id=str(uuid4()), plan_id=plan_id, **payload)
        self.database.add_device(plan_id, charger.model_dump())
        return charger

    def update(self, plan_id: str, charger_id: str, updates: dict, owner_id: str | None) -> dict:
        charger = self.get_or_404(plan_id, charger_id, owner_id)
        payload = {key: value for key, value in updates.items() if value is not None}
        if "name" in payload:
            payload["name"] = payload["name"].strip()
        if payload:
            self.database.update_device(charger_id, payload)
        refreshed = self.database.get_device(charger_id)
        if refreshed is None:
            raise HTTPException(status_code=404, detail="Carregador não encontrado.")
        return {**refreshed, "telemetry": self.snapshot(refreshed)}

    def delete(self, plan_id: str, charger_id: str, code: str | None, owner_id: str | None) -> None:
        charger = self.get_or_404(plan_id, charger_id, owner_id)
        if charger.get("kind") == "real":
            stored_code = charger.get("code") or (charger.get("metadata") or {}).get("code")
            if not code:
                raise HTTPException(status_code=400, detail="Informe o código do carregador para confirmar a exclusão.")
            if code != stored_code:
                raise HTTPException(status_code=403, detail="Código de exclusão inválido para este carregador real.")
        self.database.deactivate_device(charger_id)
