from __future__ import annotations

import hashlib
from datetime import datetime, timezone


STATUSES = ["available", "preparing", "charging", "suspended", "finished", "faulted", "offline"]
FAULTS = {1: "Falha de comunicação CAN", 2: "Sobretensão", 4: "Sobrecorrente", 8: "Subtensão", 16: "Falha de conexão do cabo", 32: "Falha de aterramento"}


def snapshot_for(charger: dict, bucket: int | None = None) -> dict:
    now = datetime.now(timezone.utc)
    bucket = bucket or int(now.timestamp() // 10)
    digest = hashlib.sha256(f"{charger['id']}:{bucket}".encode()).digest()
    status = STATUSES[digest[0] % len(STATUSES)]
    power_limit = float(charger.get("power_kw") or 11)
    phase = charger.get("phase") or ("single" if power_limit == 7 else "three")
    voltage = 230.0 if phase == "single" else 400.0
    power = round(power_limit * (0.35 + (digest[1] / 255) * 0.55), 2) if status == "charging" else 0.0
    current = round(power * 1000 / voltage, 2) if power else 0.0
    fault_code = 2 if status == "faulted" else 0
    alarm_code = 1 if digest[2] % 11 == 0 and status not in {"offline", "faulted"} else 0
    return {"status": status, "connection_status": "connected" if status not in {"offline"} else "disconnected", "power_kw": power, "voltage_v": voltage, "current_a": current, "energy_kwh": round(12 + (digest[3] / 255) * 240, 1), "session_energy_kwh": round((digest[4] / 255) * 28, 2) if status in {"charging", "finished"} else 0.0, "temperature_c": round(24 + (digest[5] / 255) * 24 + (4 if status == "charging" else 0), 1), "fault_code": fault_code, "alarm_code": alarm_code, "source": "mock", "recorded_at": now.isoformat(), "fault_description": FAULTS.get(fault_code)}
