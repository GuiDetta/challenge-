from __future__ import annotations

import hashlib
from datetime import datetime, timezone


STATUSES = ["available", "preparing", "charging", "suspended", "finished", "faulted", "offline"]
FAULTS = {
    1: "Falha de comunicação CAN",
    2: "Sobretensão",
    4: "Sobrecorrente",
    8: "Subtensão",
    16: "Falha de conexão do cabo",
    32: "Falha de aterramento",
}


def _charger_kind(charger: dict) -> str:
    metadata = charger.get("metadata") or {}
    if isinstance(metadata, dict):
        kind = metadata.get("kind")
        if kind in {"real", "simulated"}:
            return kind
    raw_kind = charger.get("kind")
    if raw_kind in {"real", "simulated"}:
        return raw_kind
    return "simulated"


def _fault_for(seed_value: int, power_limit: float) -> tuple[int, str | None]:
    fault_map = [
        (4, FAULTS[4]),
        (8, FAULTS[8]),
        (16, FAULTS[16]),
        (2, FAULTS[2]),
    ]
    fault_code, description = fault_map[seed_value % len(fault_map)]
    if power_limit >= 22 and seed_value % 5 == 0:
        return 2, FAULTS[2]
    if seed_value % 3 == 0:
        return fault_code, description
    return 0, None


def snapshot_for(charger: dict, bucket: int | None = None) -> dict:
    now = datetime.now(timezone.utc)
    bucket = bucket or int(now.timestamp() // 1800)
    power_limit = float(charger.get("power_kw") or 11)
    phase = charger.get("phase") or ("single" if power_limit == 7 else "three")
    voltage = 230.0 if phase == "single" else 400.0
    kind = _charger_kind(charger)
    seed = int.from_bytes(
        hashlib.sha256(f"{charger['id']}:{kind}:{bucket}".encode()).digest()[:4],
        byteorder="big",
    )

    payment_active = (charger.get("metadata") or {}).get("payment_active") == "true"
    if kind == "real" and not payment_active:
        status = "available"
    elif kind == "real":
        status = "charging"
    else:
        score = seed % 100
        if score < 36:
            status = "available"
        elif score < 52:
            status = "preparing"
        elif score < 79:
            status = "charging"
        elif score < 90:
            status = "finished"
        elif score < 96:
            status = "suspended"
        else:
            status = "faulted"

    if status == "charging":
        power = round(power_limit * (0.68 + ((seed % 27) / 100)), 2)
        current = round(power * 1000 / voltage, 2)
        session_energy = round(power * 0.42 + (seed % 6) * 0.6, 2)
        total_energy = round(14 + (seed % 90) + power_limit * 1.35 + session_energy, 1)
        temperature = round(26 + power_limit * 1.7 + (seed % 12) * 1.2, 1)
        connection_status = "connected"
        fault_code = 0
        alarm_code = 0 if (seed % 19) != 0 else 1
    elif status == "preparing":
        power = round(power_limit * 0.08, 2)
        current = round(power * 1000 / voltage, 2)
        session_energy = round((seed % 4) * 0.8, 2)
        total_energy = round(14 + (seed % 70) + power_limit * 1.1, 1)
        temperature = round(24 + power_limit * 0.8 + (seed % 7) * 0.9, 1)
        connection_status = "connected"
        fault_code = 0
        alarm_code = 0
    elif status == "finished":
        power = 0.0
        current = 0.0
        session_energy = round(power_limit * (0.45 + ((seed % 11) / 100)), 2)
        total_energy = round(20 + (seed % 150) + power_limit * 1.7 + session_energy, 1)
        temperature = round(27 + power_limit * 0.75 + (seed % 6) * 0.8, 1)
        connection_status = "connected"
        fault_code = 0
        alarm_code = 0
    elif status == "suspended":
        power = round(power_limit * 0.12, 2)
        current = round(power * 1000 / voltage, 2)
        session_energy = round(power_limit * 0.2 + (seed % 5) * 0.5, 2)
        total_energy = round(14 + (seed % 110) + power_limit * 1.35 + session_energy, 1)
        temperature = round(29 + power_limit * 1.2 + (seed % 9) * 1.4, 1)
        connection_status = "connected"
        fault_code = 0
        alarm_code = 0 if (seed % 21) != 0 else 1
    elif status == "faulted":
        power = 0.0
        current = 0.0
        session_energy = round(power_limit * (0.26 + ((seed % 9) / 100)), 2)
        total_energy = round(18 + (seed % 120) + power_limit * 1.55 + session_energy, 1)
        temperature = round(57 + power_limit * 1.2 + (seed % 8) * 1.5, 1)
        connection_status = "connected"
        fault_code, fault_description = _fault_for(seed, power_limit)
        if not fault_description:
            fault_code = 0
            fault_description = None
        alarm_code = fault_code or 0
    elif status == "available":
        power = 0.0
        current = 0.0
        session_energy = 0.0
        total_energy = round(12 + (seed % 120) + power_limit * 1.1, 1)
        temperature = round(23 + power_limit * 0.5 + (seed % 6) * 0.8, 1)
        connection_status = "disconnected"
        fault_code = 0
        alarm_code = 0

    if kind == "real" and not payment_active:
        power = 0.0
        current = 0.0
        session_energy = 0.0
        total_energy = 0.0
        temperature = 0.0
    else:
        power = 0.0
        current = 0.0
        session_energy = 0.0
        total_energy = round(12 + (seed % 110) + power_limit, 1)
        temperature = round(25 + power_limit * 0.7 + (seed % 10), 1)
        connection_status = "disconnected"
        fault_code = 0
        alarm_code = 0

    if status == "faulted" and fault_code == 0:
        status = "available"
        connection_status = "disconnected"
        power = 0.0
        current = 0.0
        session_energy = 0.0
        total_energy = round(12 + (seed % 120) + power_limit * 1.1, 1)
        temperature = round(23 + power_limit * 0.5 + (seed % 6) * 0.8, 1)
        fault_description = None

    return {
        "status": status,
        "connection_status": connection_status,
        "power_kw": power,
        "voltage_v": voltage,
        "current_a": current,
        "energy_kwh": round(total_energy, 1),
        "session_energy_kwh": round(session_energy, 2),
        "temperature_c": round(temperature, 1),
        "fault_code": fault_code,
        "alarm_code": alarm_code,
        "source": "modbus" if kind == "real" else "mock",
        "recorded_at": now.isoformat(),
        "fault_description": fault_description if status == "faulted" else None,
    }
