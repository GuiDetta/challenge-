from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import app

client = TestClient(app)


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
