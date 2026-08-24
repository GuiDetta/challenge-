from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.database import Database
from app.models import Alarm, AssistantChatRequest, AssistantChatResponse, Charger, ChargerCreate, ChargerSnapshot, ChargerWithSnapshot, ChargingOrderCreate, ChargingSession, Device, DeviceCreate, PlanMap, PublicCharger, UserCreate, UserLogin, WalletTopUp
from app.services.plan_processor import PlanProcessor
from app.services.charger_simulator import FAULTS, snapshot_for
from app.storage import LocalStore

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


class ChargerPositionUpdate(BaseModel):
    name: str | None = None
    x: float | None = None
    y: float | None = None
    room_id: str | None = None

store = LocalStore(BASE_DIR / "data")
database = Database(BASE_DIR / "data" / "goodwe.sqlite3")
processor = PlanProcessor()
app = FastAPI(title="GoodWe EV Plan API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_plan_or_404(plan_id: str) -> dict:
    plan = database.get_plan(plan_id) or store.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Planta não encontrada.")
    return plan


def assistant_context(owner_id: str) -> dict:
    database.complete_due_orders()
    plans = database.list_plans_for_owner(owner_id)
    chargers = []
    for plan in plans:
        for charger in database.list_devices(plan["plan_id"], "charger", owner_id, True):
            chargers.append({**charger, "telemetry": snapshot_for_charger(charger)})
    return {
        "estabelecimento": "Mapa do estabelecimento",
        "plantas": [{"plan_id": plan["plan_id"], "rooms": plan["rooms"]} for plan in plans],
        "carregadores": chargers,
        "relatorios": database.report_summary(owner_id),
        "pagamentos": database.assistant_orders(owner_id),
        "documentacao": (BASE_DIR.parent / "backend" / "README.md").read_text(encoding="utf-8")[:12000],
    }


def system_alerts(context: dict) -> list[str]:
    alerts = []
    for charger in context["carregadores"]:
        telemetry = charger.get("telemetry", {})
        if not charger.get("active", True):
            continue
        if telemetry.get("status") in {"faulted", "offline"}:
            alerts.append(f"{charger['name']} está em estado {telemetry['status']}.")
    if 18 <= datetime.now().astimezone().hour < 22:
        alerts.append("Horário de pico ativo: a tarifa vigente pode ser maior.")
    return alerts


def local_assistant_answer(message: str, context: dict) -> str:
    lowered = message.lower()
    chargers = context["carregadores"]
    if "quant" in lowered and "carreg" in lowered:
        return f"Você tem {sum(1 for charger in chargers if charger.get('active', True))} carregador(es) ativo(s)."
    if "relat" in lowered or "fatur" in lowered:
        report = context["relatorios"]
        return f"O relatório registra R$ {report['revenue_total']:.2f} em receita e {report['month_energy_kwh']:.2f} kWh no mês."
    if "pag" in lowered:
        return f"Encontrei {len(context['pagamentos'])} pagamento(s) ou pedido(s) registrado(s)."
    return "Estou em modo local. Configure OPENAI_API_KEY no backend para ativar o ECOTWIN Chatbot com respostas inteligentes sobre seus dados."


@app.get("/api/assistant/alerts")
def assistant_alerts(owner_id: str = Query(..., min_length=1)) -> dict[str, list[str]]:
    return {"alerts": system_alerts(assistant_context(owner_id))}


@app.post("/api/assistant/chat", response_model=AssistantChatResponse)
def assistant_chat(request: AssistantChatRequest) -> AssistantChatResponse:
    context = assistant_context(request.owner_id)
    alerts = system_alerts(context)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return AssistantChatResponse(content=local_assistant_answer(request.message, context), system_alerts=alerts, provider="local")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            instructions="Você é o ECOTWIN Chatbot. Responda em português do Brasil, de forma objetiva. Use somente o contexto fornecido. Não invente dados, não revele segredos e diferencie fatos de sugestões.",
            input=[
                {"role": "system", "content": f"Contexto privado do lojista em JSON:\n{json.dumps(context, ensure_ascii=False, default=str)}"},
                *[{"role": item.role, "content": item.content} for item in request.history[-20:]],
                {"role": "user", "content": request.message},
            ],
        )
        return AssistantChatResponse(content=response.output_text, system_alerts=alerts, provider="openai")
    except Exception:
        return AssistantChatResponse(content="Não consegui acessar o ECOTWIN Chatbot agora. Verifique a configuração da OpenAI e tente novamente.", system_alerts=alerts, provider="local")


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


@app.get("/api/plans", response_model=list[PlanMap])
def list_owned_plans(owner_id: str = Query(..., min_length=1)) -> list[dict]:
    return database.list_plans_for_owner(owner_id)


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


def charger_with_live_session(charger: dict) -> dict:
    session = database.get_active_order_for_charger(charger["code"])
    telemetry = snapshot_for_charger(charger)
    if session:
        return {**charger, "telemetry": telemetry, "active_session_started_at": session["created_at"], "active_session_duration_minutes": session["estimated_duration_minutes"], "active_session_energy_kwh": session["energy_kwh"]}
    return {**charger, "telemetry": telemetry}


@app.get("/api/chargegrid/{code}", response_model=PublicCharger)
def public_charger(code: str) -> dict:
    database.complete_due_orders()
    charger = database.get_charger_by_code(code.upper())
    if charger is None:
        raise HTTPException(status_code=404, detail="Carregador real não encontrado.")
    live = charger_with_live_session(charger)
    return {key: live.get(key) for key in ("code", "name", "model", "power_kw", "telemetry", "active_session_started_at", "active_session_duration_minutes", "active_session_energy_kwh")} | {"status": live["telemetry"]["status"]}


@app.post("/api/auth/register", status_code=201)
def register_user(user_input: UserCreate) -> dict:
    try:
        return database.create_user({"id": str(uuid4()), **user_input.model_dump()})
    except Exception as error:
        if "UNIQUE" in str(error).upper():
            raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado.") from error
        raise


@app.post("/api/auth/login")
def login_user(user_input: UserLogin) -> dict:
    user = database.authenticate_user(user_input.email, user_input.password)
    if user is None:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
    return user


@app.post("/api/charging-orders", status_code=201)
def create_charging_order(order_input: ChargingOrderCreate) -> dict:
    if database.get_user(order_input.user_id) is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    charger = database.get_charger_by_code(order_input.charger_code.upper())
    if charger is None:
        raise HTTPException(status_code=404, detail="Carregador real não encontrado.")
    database.activate_charger_by_code(order_input.charger_code.upper())
    now = datetime.now().astimezone()
    is_peak = 18 <= now.hour < 22
    price_per_kwh = 2.79 if is_peak else 1.99
    estimated_duration_minutes = max(1, round(order_input.energy_kwh / float(charger["power_kw"] or 11) * 60))
    order = {"id": str(uuid4()), **order_input.model_dump(), "charger_code": order_input.charger_code.upper(), "price_per_kwh": price_per_kwh, "scheduled_at": now.isoformat(), "estimated_duration_minutes": estimated_duration_minutes, "total_amount": round(order_input.energy_kwh * price_per_kwh, 2)}
    return database.create_order(order)


@app.post("/api/wallet/top-ups", status_code=201)
def top_up_wallet(top_up: WalletTopUp) -> dict:
    if database.get_user(top_up.user_id) is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return database.add_wallet_transaction({"id": str(uuid4()), "user_id": top_up.user_id, "amount": top_up.amount, "type": "top_up"})


@app.get("/api/reports/summary")
def reports_summary(owner_id: str | None = Query(default=None)) -> dict:
    return database.report_summary(owner_id)


@app.get("/api/plans/{plan_id}/chargers", response_model=list[ChargerWithSnapshot])
def list_chargers(plan_id: str, owner_id: str | None = Query(default=None), include_inactive: bool = Query(default=False)) -> list[dict]:
    get_plan_or_404(plan_id)
    database.complete_due_orders()
    chargers = []
    for charger in database.list_devices(plan_id, "charger", owner_id, include_inactive):
        chargers.append(charger_with_live_session(charger))
    return chargers


@app.get("/api/chargers", response_model=list[ChargerWithSnapshot])
def list_all_real_chargers(owner_id: str = Query(..., min_length=1), include_inactive: bool = Query(default=False)) -> list[dict]:
    database.complete_due_orders()
    chargers = []
    for charger in database.list_real_chargers(owner_id, include_inactive):
        chargers.append(charger_with_live_session(charger))
    return chargers


@app.post("/api/plans/{plan_id}/chargers", response_model=Charger, status_code=201)
def create_charger(plan_id: str, charger_input: ChargerCreate, x_user_id: str | None = Header(default=None)) -> Charger:
    plan = get_plan_or_404(plan_id)
    if charger_input.x > plan["width"] or charger_input.y > plan["height"]:
        raise HTTPException(status_code=422, detail="A posição do carregador está fora dos limites da planta.")
    payload = charger_input.model_dump()
    payload["owner_id"] = x_user_id or payload.get("owner_id")
    code = payload.get("code") or Database.generate_device_code()
    payload["code"] = code
    payload["metadata"] = {**charger_input.metadata, "kind": charger_input.kind, "code": code, "payment_active": "false" if charger_input.kind == "real" else "true"}
    charger = Charger(id=str(uuid4()), plan_id=plan_id, **payload)
    database.add_device(plan_id, charger.model_dump())
    return charger


@app.patch("/api/plans/{plan_id}/chargers/{charger_id}", response_model=ChargerWithSnapshot)
def update_charger(plan_id: str, charger_id: str, updates: ChargerPositionUpdate) -> dict:
    charger = charger_or_404(plan_id, charger_id)
    payload: dict[str, object] = {}
    if updates.name is not None:
        payload["name"] = updates.name.strip()
    if updates.x is not None:
        payload["x"] = updates.x
    if updates.y is not None:
        payload["y"] = updates.y
    if updates.room_id is not None:
        payload["room_id"] = updates.room_id
    if payload:
        database.update_device(charger_id, payload)
    refreshed = database.get_device(charger_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Carregador não encontrado.")
    return {**refreshed, "telemetry": snapshot_for_charger(refreshed)}


@app.delete("/api/plans/{plan_id}/chargers/{charger_id}", status_code=204)
async def delete_charger(
    plan_id: str,
    charger_id: str,
    request: Request,
    code: str | None = Query(default=None),
    payload: dict[str, str] | None = Body(default=None),
) -> None:
    charger = charger_or_404(plan_id, charger_id)
    request_code = code
    if request_code is None and payload is not None:
        request_code = (payload or {}).get("code")
    if request_code is None:
        try:
            raw_body = await request.body()
            if raw_body:
                text = raw_body.decode("utf-8", errors="ignore")
                if text:
                    data = json.loads(text)
                    if isinstance(data, dict):
                        request_code = data.get("code")
        except (json.JSONDecodeError, ValueError):
            request_code = None

    if charger.get("kind") == "real":
        stored_code = charger.get("code") or (charger.get("metadata") or {}).get("code")
        if not request_code:
            raise HTTPException(status_code=400, detail="Informe o código do carregador para confirmar a exclusão.")
        if request_code != stored_code:
            raise HTTPException(status_code=403, detail="Código de exclusão inválido para este carregador real.")
    database.deactivate_device(charger_id)


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
