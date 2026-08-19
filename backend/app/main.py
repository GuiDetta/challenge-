from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.database import Database
from app.models import Alarm, Charger, ChargerCreate, ChargerSnapshot, ChargerWithSnapshot, ChargingSession, Device, DeviceCreate, PlanMap
from app.services.plan_processor import PlanProcessor
from app.services.charger_simulator import FAULTS, snapshot_for
from app.storage import LocalStore

BASE_DIR = Path(__file__).resolve().parents[1]
store = LocalStore(BASE_DIR / "data")
database = Database(BASE_DIR / "data" / "goodwe.sqlite3")
processor = PlanProcessor()
app = FastAPI(title="GoodWe EV Plan API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def get_plan_or_404(plan_id: str) -> dict:
    plan = database.get_plan(plan_id) or store.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Planta não encontrada.")
    return plan


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/plans", response_model=PlanMap, status_code=201)
async def upload_plan(file: UploadFile = File(...)) -> PlanMap:
    if file.content_type not in {"image/png", "image/jpeg", "image/webp", "image/bmp"}:
        raise HTTPException(status_code=415, detail="Envie uma planta em PNG, JPEG, WEBP ou BMP.")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="O arquivo enviado está vazio.")
    plan_id = str(uuid4())
    image_path = store.save_image(plan_id, content)
    try:
        image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError("Arquivo de imagem inválido.")
        plan = processor.process(image_path, plan_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    payload = plan.model_dump()
    room_id_map = {room["id"]: f"{plan_id}-{room['id']}" for room in payload["rooms"]}
    for room in payload["rooms"]:
        room["id"] = room_id_map[room["id"]]
    for previous_id, global_id in room_id_map.items():
        payload["svg"] = payload["svg"].replace(f'data-room-id="{previous_id}"', f'data-room-id="{global_id}"')
    database.save_plan(payload, file.filename or "planta")
    store.save_plan(plan_id, {**payload, "devices": []})
    return PlanMap(**payload)


@app.get("/api/plans/{plan_id}", response_model=PlanMap)
def get_plan(plan_id: str) -> dict:
    return get_plan_or_404(plan_id)


@app.get("/api/plans/{plan_id}/devices", response_model=list[Device])
def list_devices(plan_id: str) -> list[dict]:
    get_plan_or_404(plan_id)
    return database.list_devices(plan_id)


@app.post("/api/plans/{plan_id}/devices", response_model=Device, status_code=201)
def add_device(plan_id: str, device_input: DeviceCreate) -> Device:
    plan = get_plan_or_404(plan_id)
    if device_input.x > plan["width"] or device_input.y > plan["height"]:
        raise HTTPException(status_code=422, detail="A posição do dispositivo está fora dos limites da planta.")
    device = Device(id=str(uuid4()), plan_id=plan_id, **device_input.model_dump())
    database.add_device(plan_id, {**device.model_dump(), "device_type": device_input.device_type})
    return device


@app.delete("/api/plans/{plan_id}/devices/{device_id}", status_code=204)
def delete_device(plan_id: str, device_id: str) -> None:
    get_plan_or_404(plan_id)
    device = database.get_device(device_id)
    if device is None or device["plan_id"] != plan_id:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")
    database.delete_device(device_id)


def charger_or_404(plan_id: str, charger_id: str) -> dict:
    charger = database.get_device(charger_id)
    if charger is None or charger["plan_id"] != plan_id or charger["device_type"] != "charger":
        raise HTTPException(status_code=404, detail="Carregador não encontrado.")
    return charger


def snapshot_for_charger(charger: dict) -> dict:
    snapshot = snapshot_for(charger)
    database.save_snapshot(charger["id"], snapshot)
    if snapshot["fault_code"]:
        database.save_alarm({"id": f"{charger['id']}-{snapshot['fault_code']}", "charger_id": charger["id"], "code": snapshot["fault_code"], "severity": "critical", "title": FAULTS.get(snapshot["fault_code"], "Falha do carregador"), "detail": snapshot.get("fault_description") or "Falha simulada pelo monitoramento.", "active": True, "created_at": snapshot["recorded_at"]})
    return snapshot


@app.get("/api/plans/{plan_id}/chargers", response_model=list[ChargerWithSnapshot])
def list_chargers(plan_id: str) -> list[dict]:
    get_plan_or_404(plan_id)
    chargers = []
    for charger in database.list_devices(plan_id, "charger"):
        telemetry = snapshot_for_charger(charger)
        chargers.append({**charger, "telemetry": telemetry})
    return chargers


@app.post("/api/plans/{plan_id}/chargers", response_model=Charger, status_code=201)
def create_charger(plan_id: str, charger_input: ChargerCreate) -> Charger:
    plan = get_plan_or_404(plan_id)
    if charger_input.x > plan["width"] or charger_input.y > plan["height"]:
        raise HTTPException(status_code=422, detail="A posição do carregador está fora dos limites da planta.")
    charger = Charger(id=str(uuid4()), plan_id=plan_id, **charger_input.model_dump())
    database.add_device(plan_id, charger.model_dump())
    return charger


@app.get("/api/plans/{plan_id}/chargers/{charger_id}/telemetry", response_model=ChargerSnapshot)
def charger_telemetry(plan_id: str, charger_id: str) -> ChargerSnapshot:
    charger = charger_or_404(plan_id, charger_id)
    return snapshot_for_charger(charger)


@app.get("/api/plans/{plan_id}/chargers/{charger_id}/telemetry/history", response_model=list[ChargerSnapshot])
def charger_telemetry_history(plan_id: str, charger_id: str, limit: int = 50) -> list[dict]:
    charger_or_404(plan_id, charger_id)
    return database.list_snapshots(charger_id, max(1, min(limit, 500)))


@app.get("/api/plans/{plan_id}/alarms", response_model=list[Alarm])
def list_alarms(plan_id: str, active_only: bool = False) -> list[dict]:
    get_plan_or_404(plan_id)
    return database.list_alarms(plan_id, active_only)


@app.get("/api/plans/{plan_id}/sessions", response_model=list[ChargingSession])
def list_sessions(plan_id: str) -> list[dict]:
    get_plan_or_404(plan_id)
    return database.list_sessions(plan_id)


@app.post("/api/plans/{plan_id}/simulation/tick", response_model=list[ChargerWithSnapshot])
def simulation_tick(plan_id: str) -> list[dict]:
    return list_chargers(plan_id)
