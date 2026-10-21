from datetime import datetime
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import app
from app.services import order_service

client = TestClient(app)


@pytest.fixture
def off_peak(monkeypatch: pytest.MonkeyPatch) -> None:
    # os valores esperados usam a tarifa fora de pico; sem isso a suíte falha depois das 18h
    real_tariff = order_service.current_tariff
    monkeypatch.setattr(order_service, "current_tariff", lambda now=None: real_tariff((now or datetime.now().astimezone()).replace(hour=10)))


def new_real_charger(owner_id: str, name: str) -> dict:
    image = Image.new("RGB", (160, 120), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    plan = client.post("/api/plans", files={"file": (f"{name}.png", buffer.getvalue(), "image/png")}, headers={"X-User-Id": owner_id}).json()
    return client.post(f"/api/plans/{plan['plan_id']}/chargers", json={"name": name, "x": 30, "y": 40, "kind": "real"}, headers={"X-User-Id": owner_id}).json()


def new_driver(prefix: str) -> dict:
    return client.post("/api/auth/register", json={"name": "Motorista", "email": f"{prefix}-{uuid4().hex}@example.com", "password": "secret123", "role": "cliente"}).json()


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_rejects_non_image() -> None:
    response = client.post("/api/plans", files={"file": ("plan.txt", b"not an image", "text/plain")})
    assert response.status_code == 415


def test_upload_and_add_device() -> None:
    image = Image.new("RGB", (120, 100), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    response = client.post("/api/plans", files={"file": ("plan.png", buffer.getvalue(), "image/png")})
    assert response.status_code == 201
    plan = response.json()
    device_response = client.post(f"/api/plans/{plan['plan_id']}/devices", json={"name": "Entrada", "x": 40, "y": 30})
    assert device_response.status_code == 201
    assert device_response.json()["plan_id"] == plan["plan_id"]


def test_plans_are_isolated_by_owner() -> None:
    image = Image.new("RGB", (120, 100), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    response = client.post(
        "/api/plans",
        files={"file": ("private-plan.png", buffer.getvalue(), "image/png")},
        headers={"X-User-Id": "owner-a"},
    )
    assert response.status_code == 201
    plan_id = response.json()["plan_id"]

    assert client.get(f"/api/plans/{plan_id}?owner_id=owner-a").status_code == 200
    assert client.get(f"/api/plans/{plan_id}?owner_id=owner-b").status_code == 404
    assert client.get("/api/plans?owner_id=owner-b").json() == []


def test_charging_order_requires_and_debits_wallet_balance(off_peak: None) -> None:
    email = f"wallet-{uuid4().hex}@example.com"
    user = client.post(
        "/api/auth/register",
        json={"name": "Wallet User", "email": email, "password": "secret123", "role": "cliente"},
    ).json()
    image = Image.new("RGB", (160, 120), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    plan = client.post(
        "/api/plans",
        files={"file": ("wallet-plan.png", buffer.getvalue(), "image/png")},
        headers={"X-User-Id": user["id"]},
    ).json()
    charger = client.post(
        f"/api/plans/{plan['plan_id']}/chargers",
        json={"name": "Wallet Charger", "x": 30, "y": 40, "kind": "real"},
        headers={"X-User-Id": user["id"]},
    ).json()
    order = {"user_id": user["id"], "charger_code": charger["code"], "energy_kwh": 10, "payment_method": "wallet"}

    assert client.post("/api/charging-orders", json=order).status_code == 402
    assert client.post(f"/api/wallet/top-ups", json={"user_id": user["id"], "amount": 25}).status_code == 201
    assert client.post("/api/charging-orders", json=order).status_code == 201
    assert client.post("/api/charging-orders", json=order).status_code == 402


def test_finishing_order_refunds_undelivered_energy(off_peak: None) -> None:
    email = f"refund-{uuid4().hex}@example.com"
    user = client.post(
        "/api/auth/register",
        json={"name": "Refund User", "email": email, "password": "secret123", "role": "cliente"},
    ).json()
    image = Image.new("RGB", (160, 120), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    plan = client.post(
        "/api/plans",
        files={"file": ("refund-plan.png", buffer.getvalue(), "image/png")},
        headers={"X-User-Id": user["id"]},
    ).json()
    charger = client.post(
        f"/api/plans/{plan['plan_id']}/chargers",
        json={"name": "Refund Charger", "x": 30, "y": 40, "kind": "real"},
        headers={"X-User-Id": user["id"]},
    ).json()
    order = {"user_id": user["id"], "charger_code": charger["code"], "energy_kwh": 10, "payment_method": "wallet"}
    client.post("/api/wallet/top-ups", json={"user_id": user["id"], "amount": 25})
    created = client.post("/api/charging-orders", json=order).json()

    finished = client.post(
        f"/api/charging-orders/{created['id']}/finish",
        json={"user_id": user["id"], "energy_delivered_kwh": 5},
    )
    assert finished.status_code == 200
    assert finished.json()["refund_amount"] == 9.95
    assert finished.json()["wallet_balance"] == 15.05
    public_status = client.get(f"/api/chargegrid/{charger['code']}")
    assert public_status.status_code == 200
    assert public_status.json()["status"] == "available"


def test_operations_report_covers_availability_faults_occupancy_and_demand() -> None:
    email = f"ops-{uuid4().hex}@example.com"
    user = client.post(
        "/api/auth/register",
        json={"name": "Ops User", "email": email, "password": "secret123", "role": "lojista"},
    ).json()
    image = Image.new("RGB", (160, 120), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    plan = client.post(
        "/api/plans",
        files={"file": ("ops-plan.png", buffer.getvalue(), "image/png")},
        headers={"X-User-Id": user["id"]},
    ).json()
    client.post(
        f"/api/plans/{plan['plan_id']}/chargers",
        json={"name": "Ops Charger", "x": 30, "y": 40, "kind": "real", "power_kw": 22, "phase": "three"},
        headers={"X-User-Id": user["id"]},
    )
    client.post(f"/api/plans/{plan['plan_id']}/simulation/tick")

    response = client.get(f"/api/reports/operations?owner_id={user['id']}&days=7&contracted_kw=30")
    assert response.status_code == 200
    report = response.json()

    assert report["days"] == 7
    assert report["availability"]["samples"] >= 1
    assert 0 <= report["availability"]["fleet_uptime_percent"] <= 100
    assert report["demand"]["installed_kw"] == 22
    assert report["demand"]["contracted_kw"] == 30
    assert report["demand"]["peak_kw"] <= 22
    assert len(report["occupancy"]["hours"]) == 24
    for item in report["faults"]["items"]:
        assert item["first_action"]
        assert item["escalation"]


def test_operations_report_is_isolated_by_owner() -> None:
    response = client.get(f"/api/reports/operations?owner_id=owner-sem-dados-{uuid4().hex}")
    assert response.status_code == 200
    report = response.json()
    assert report["availability"]["chargers"] == []
    assert report["occupancy"]["total_sessions"] == 0
    assert report["demand"]["installed_kw"] == 0


def test_failed_request_is_logged_with_code_and_reference() -> None:
    owner = f"dono-{uuid4().hex}"
    response = client.post(
        "/api/charging-orders",
        json={"user_id": owner, "charger_code": "HC2-XXXXXX", "energy_kwh": 5, "payment_method": "wallet"},
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["code"] == "ECT-404"
    assert len(payload["reference"]) == 6
    assert payload["detail"]

    events = client.get(f"/api/reports/errors?owner_id={owner}&days=1&limit=50").json()["events"]
    assert any(event["reference"] == payload["reference"] for event in events)


def test_error_log_does_not_leak_between_owners() -> None:
    victim = f"vitima-{uuid4().hex}"
    client.post(
        "/api/charging-orders",
        json={"user_id": victim, "charger_code": "HC2-SEGREDO", "energy_kwh": 5, "payment_method": "wallet"},
    )
    intruder = client.get(f"/api/reports/errors?owner_id=intruso-{uuid4().hex}&days=1&limit=100").json()["events"]
    assert intruder == []

    export = client.get(f"/api/reports/export/erros?owner_id=intruso-{uuid4().hex}&days=1")
    assert export.status_code == 200
    assert len(export.content.decode("utf-8-sig").splitlines()) == 1  # só o cabeçalho


def test_validation_error_names_the_field() -> None:
    response = client.get("/api/reports/operations")
    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "ECT-422"
    assert "owner_id" in payload["detail"]


def test_exports_return_downloadable_csv() -> None:
    email = f"csv-{uuid4().hex}@example.com"
    user = client.post(
        "/api/auth/register",
        json={"name": "CSV User", "email": email, "password": "secret123", "role": "lojista"},
    ).json()
    image = Image.new("RGB", (160, 120), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    plan = client.post(
        "/api/plans",
        files={"file": ("csv-plan.png", buffer.getvalue(), "image/png")},
        headers={"X-User-Id": user["id"]},
    ).json()
    charger = client.post(
        f"/api/plans/{plan['plan_id']}/chargers",
        json={"name": "CSV Charger", "x": 30, "y": 40, "kind": "real", "power_kw": 7},
        headers={"X-User-Id": user["id"]},
    ).json()
    client.post("/api/wallet/top-ups", json={"user_id": user["id"], "amount": 100})
    client.post(
        "/api/charging-orders",
        json={"user_id": user["id"], "charger_code": charger["code"], "energy_kwh": 3, "payment_method": "wallet"},
    )

    for report in ("financeiro", "disponibilidade", "falhas", "erros"):
        response = client.get(f"/api/reports/export/{report}?owner_id={user['id']}&days=30")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment; filename=" in response.headers["content-disposition"]
        assert response.content.startswith(b"\xef\xbb\xbf")  # BOM, para o Excel ler os acentos
        assert ";" in response.content.decode("utf-8-sig").splitlines()[0]

    financial = client.get(f"/api/reports/export/financeiro?owner_id={user['id']}&days=30")
    lines = financial.content.decode("utf-8-sig").splitlines()
    assert lines[0].startswith("Data;Hora;Carregador")
    assert charger["code"] in lines[1]

    assert client.get("/api/reports/export/inexistente?owner_id=x").status_code == 404
    assert client.get("/api/reports/export/financeiro").status_code == 422
    assert client.get("/api/reports/errors").status_code == 422


def test_charger_telemetry_and_history() -> None:
    image = Image.new("RGB", (160, 120), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    upload = client.post("/api/plans", files={"file": ("plan.png", buffer.getvalue(), "image/png")})
    plan_id = upload.json()["plan_id"]
    charger = client.post(f"/api/plans/{plan_id}/chargers", json={"name": "HCA 01", "x": 70, "y": 50, "model": "GW22K-HCA-20", "power_kw": 22, "phase": "three"})
    assert charger.status_code == 201
    charger_id = charger.json()["id"]
    telemetry = client.get(f"/api/plans/{plan_id}/chargers/{charger_id}/telemetry")
    assert telemetry.status_code == 200
    assert telemetry.json()["source"] == "mock"
    assert telemetry.json()["voltage_v"] == 400
    history = client.get(f"/api/plans/{plan_id}/chargers/{charger_id}/telemetry/history")
    assert history.status_code == 200
    assert len(history.json()) >= 1
    listed = client.get(f"/api/plans/{plan_id}/chargers")
    assert listed.status_code == 200
    assert listed.json()[0]["telemetry"]["status"] in {"available", "preparing", "charging", "suspended", "finished", "faulted", "offline"}


def test_public_chargegrid_works_without_active_session() -> None:
    image = Image.new("RGB", (160, 120), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    plan = client.post(
        "/api/plans",
        files={"file": ("plan.png", buffer.getvalue(), "image/png")},
    ).json()
    charger = client.post(
        f"/api/plans/{plan['plan_id']}/chargers",
        json={"name": "HC2 QR", "x": 30, "y": 40, "kind": "real"},
    ).json()

    response = client.get(
        f"/api/chargegrid/{charger['code']}",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    assert response.json()["code"] == charger["code"]
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_active_real_charger_reports_connected_telemetry() -> None:
    image = Image.new("RGB", (160, 120), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    plan = client.post(
        "/api/plans",
        files={"file": ("active.png", buffer.getvalue(), "image/png")},
        headers={"X-User-Id": "telemetry-owner"},
    ).json()
    charger = client.post(
        f"/api/plans/{plan['plan_id']}/chargers",
        json={"name": "Active HC2", "x": 30, "y": 40, "kind": "real"},
        headers={"X-User-Id": "telemetry-owner"},
    ).json()
    user = client.post(
        "/api/auth/register",
        json={"name": "Telemetry User", "email": f"telemetry-{uuid4().hex}@example.com", "password": "secret123", "role": "cliente"},
    ).json()
    client.post("/api/wallet/top-ups", json={"user_id": user["id"], "amount": 100})
    order = client.post("/api/charging-orders", json={"user_id": user["id"], "charger_code": charger["code"], "energy_kwh": 10, "payment_method": "wallet"}).json()

    telemetry = client.get(f"/api/chargegrid/{charger['code']}").json()
    assert telemetry["status"] == "charging"
    assert telemetry["telemetry"]["connection_status"] == "connected"
    assert telemetry["telemetry"]["power_kw"] > 0
    assert telemetry["active_order_id"] is None

    current_session = client.get(f"/api/chargegrid/{charger['code']}?user_id={user['id']}").json()
    assert current_session["active_order_id"] == order["id"]

    other_user_session = client.get(f"/api/chargegrid/{charger['code']}?user_id=another-user").json()
    assert other_user_session["active_order_id"] is None


def test_charger_code_is_unique_and_required_for_real_delete() -> None:
    image = Image.new("RGB", (160, 120), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    upload = client.post("/api/plans", files={"file": ("plan.png", buffer.getvalue(), "image/png")})
    plan_id = upload.json()["plan_id"]
    charger = client.post(f"/api/plans/{plan_id}/chargers", json={"name": "HC2 Real", "x": 30, "y": 40, "kind": "real"})
    assert charger.status_code == 201
    payload = charger.json()
    assert payload["code"].startswith("HC2-")

    invalid_delete = client.request(
        "DELETE",
        f"/api/plans/{plan_id}/chargers/{payload['id']}",
        json={"code": "ERRADO"},
    )
    assert invalid_delete.status_code == 403

    valid_delete = client.request(
        "DELETE",
        f"/api/plans/{plan_id}/chargers/{payload['id']}",
        json={"code": payload["code"]},
    )
    assert valid_delete.status_code == 204

    listed = client.get(f"/api/plans/{plan_id}/chargers")
    assert listed.status_code == 200
    assert listed.json() == []


def test_upload_detects_parking_slots() -> None:
    image = Image.new("RGB", (720, 520), "white")
    draw = ImageDraw.Draw(image)
    for x in range(140, 620, 100):
        draw.line((x, 30, x, 470), fill="black", width=3)
    for y in range(90, 440, 80):
        draw.line((40, y, 660, y), fill="black", width=3)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    response = client.post("/api/plans", files={"file": ("parking.png", buffer.getvalue(), "image/png")})
    assert response.status_code == 201
    plan = response.json()
    assert len(plan["rooms"]) >= 4
    assert all(room["name"].startswith("Vaga") for room in plan["rooms"][:3])


def test_tariff_changes_at_peak_hours() -> None:
    morning = order_service.current_tariff(datetime(2026, 10, 20, 10, 0).astimezone())
    evening = order_service.current_tariff(datetime(2026, 10, 20, 19, 0).astimezone())
    night = order_service.current_tariff(datetime(2026, 10, 20, 23, 0).astimezone())
    assert (morning["price_per_kwh"], morning["is_peak"]) == (1.99, False)
    assert (evening["price_per_kwh"], evening["is_peak"]) == (2.79, True)
    assert evening["next_change_at"].startswith("2026-10-20T22:00")
    assert night["next_change_at"].startswith("2026-10-21T18:00")
    assert client.get("/api/tariff").json()["price_per_kwh"] in (1.99, 2.79)


def test_wallet_statement_lists_top_ups_debits_and_refunds(off_peak: None) -> None:
    charger = new_real_charger("statement-owner", "Statement HC2")
    user = new_driver("statement")
    top_up = client.post("/api/wallet/top-ups", json={"user_id": user["id"], "amount": 50, "method": "card"})
    assert top_up.status_code == 201
    assert top_up.json()["wallet_balance"] == 50
    order = client.post("/api/charging-orders", json={"user_id": user["id"], "charger_code": charger["code"], "energy_kwh": 10, "payment_method": "wallet"}).json()
    client.post(f"/api/charging-orders/{order['id']}/finish", json={"user_id": user["id"], "energy_delivered_kwh": 5})

    statement = client.get(f"/api/wallet/{user['id']}").json()
    assert statement["balance"] == 40.05
    assert sorted(item["method"] for item in statement["transactions"]) == ["card", "charge", "refund"]


def test_order_history_only_shows_own_orders(off_peak: None) -> None:
    charger = new_real_charger("history-owner", "History HC2")
    user = new_driver("history")
    other = new_driver("history-other")
    for driver in (user, other):
        client.post("/api/wallet/top-ups", json={"user_id": driver["id"], "amount": 25})
    client.post("/api/charging-orders", json={"user_id": user["id"], "charger_code": charger["code"], "energy_kwh": 2, "payment_method": "wallet"})

    history = client.get(f"/api/charging-orders?user_id={user['id']}").json()
    assert len(history) == 1
    assert history[0]["charger_name"] == "History HC2"
    assert client.get(f"/api/charging-orders?user_id={other['id']}").json() == []
    assert client.get("/api/wallet/nao-existe").status_code == 404


def test_plan_processor_reads_image_from_accented_path(tmp_path) -> None:
    from app.services.plan_processor import PlanProcessor

    folder = tmp_path / "Área de Trabalho"
    folder.mkdir()
    image = Image.new("RGB", (200, 150), "white")
    ImageDraw.Draw(image).rectangle((20, 20, 180, 130), outline="black", width=4)
    path = folder / "planta.png"
    image.save(path)

    plan = PlanProcessor().process(path, "plano-acento")
    assert (plan.width, plan.height) == (200, 150)
