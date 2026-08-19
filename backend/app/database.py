from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    svg TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    ocr_available INTEGER NOT NULL DEFAULT 0,
                    warnings_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rooms (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    polygon_json TEXT NOT NULL,
                    bounds_json TEXT NOT NULL,
                    area REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
                    room_id TEXT REFERENCES rooms(id) ON DELETE SET NULL,
                    name TEXT NOT NULL,
                    device_type TEXT NOT NULL,
                    model TEXT,
                    power_kw REAL,
                    phase TEXT,
                    rated_current_a REAL,
                    x REAL NOT NULL,
                    y REAL NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS charger_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    charger_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    connection_status TEXT NOT NULL,
                    power_kw REAL NOT NULL,
                    voltage_v REAL NOT NULL,
                    current_a REAL NOT NULL,
                    energy_kwh REAL NOT NULL,
                    session_energy_kwh REAL NOT NULL,
                    temperature_c REAL NOT NULL,
                    fault_code INTEGER NOT NULL DEFAULT 0,
                    alarm_code INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'mock',
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS charging_sessions (
                    id TEXT PRIMARY KEY,
                    charger_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    status TEXT NOT NULL,
                    energy_kwh REAL NOT NULL DEFAULT 0,
                    duration_seconds INTEGER NOT NULL DEFAULT 0,
                    start_meter_kwh REAL,
                    end_meter_kwh REAL,
                    start_mode TEXT,
                    end_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS alarms (
                    id TEXT PRIMARY KEY,
                    charger_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
                    code INTEGER NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    cleared_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_rooms_plan ON rooms(plan_id);
                CREATE INDEX IF NOT EXISTS idx_devices_plan ON devices(plan_id);
                CREATE INDEX IF NOT EXISTS idx_snapshots_charger_time ON charger_snapshots(charger_id, recorded_at);
                CREATE INDEX IF NOT EXISTS idx_alarms_charger_active ON alarms(charger_id, active);
                """
            )

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def save_plan(self, plan: dict[str, Any], original_filename: str) -> None:
        with self.connect() as connection:
            connection.execute("INSERT OR REPLACE INTO plans (id, width, height, svg, original_filename, ocr_available, warnings_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (plan["plan_id"], plan["width"], plan["height"], plan["svg"], original_filename, int(plan["ocr_available"]), json.dumps(plan.get("warnings", []), ensure_ascii=False), self.now()))
            connection.execute("DELETE FROM rooms WHERE plan_id = ?", (plan["plan_id"],))
            connection.executemany("INSERT INTO rooms (id, plan_id, name, polygon_json, bounds_json, area) VALUES (?, ?, ?, ?, ?, ?)", [(room["id"], plan["plan_id"], room["name"], json.dumps(room["polygon"]), json.dumps(room["bounds"]), room["area"]) for room in plan["rooms"]])

    def get_plan(self, plan_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if row is None:
                return None
            rooms = connection.execute("SELECT * FROM rooms WHERE plan_id = ? ORDER BY id", (plan_id,)).fetchall()
        return {"plan_id": row["id"], "width": row["width"], "height": row["height"], "svg": row["svg"], "rooms": [{"id": room["id"], "name": room["name"], "polygon": json.loads(room["polygon_json"]), "bounds": json.loads(room["bounds_json"]), "area": room["area"]} for room in rooms], "walls": [], "texts": [], "ocr_available": bool(row["ocr_available"]), "warnings": json.loads(row["warnings_json"])}

    def add_device(self, plan_id: str, device: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute("INSERT INTO devices (id, plan_id, room_id, name, device_type, model, power_kw, phase, rated_current_a, x, y, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (device["id"], plan_id, device.get("room_id"), device["name"], device["device_type"], device.get("model"), device.get("power_kw"), device.get("phase"), device.get("rated_current_a"), device["x"], device["y"], json.dumps(device.get("metadata", {})), self.now()))

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        return self._device(row) if row else None

    def list_devices(self, plan_id: str, device_type: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM devices WHERE plan_id = ?"
        params: list[Any] = [plan_id]
        if device_type:
            query += " AND device_type = ?"
            params.append(device_type)
        with self.connect() as connection:
            rows = connection.execute(query + " ORDER BY name", params).fetchall()
        return [self._device(row) for row in rows]

    def delete_device(self, device_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _device(row: sqlite3.Row) -> dict[str, Any]:
        return {"id": row["id"], "plan_id": row["plan_id"], "room_id": row["room_id"], "name": row["name"], "device_type": row["device_type"], "model": row["model"], "power_kw": row["power_kw"], "phase": row["phase"], "rated_current_a": row["rated_current_a"], "x": row["x"], "y": row["y"], "metadata": json.loads(row["metadata_json"])}

    def save_snapshot(self, charger_id: str, snapshot: dict[str, Any]) -> int:
        with self.connect() as connection:
            cursor = connection.execute("INSERT INTO charger_snapshots (charger_id, status, connection_status, power_kw, voltage_v, current_a, energy_kwh, session_energy_kwh, temperature_c, fault_code, alarm_code, source, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (charger_id, snapshot["status"], snapshot["connection_status"], snapshot["power_kw"], snapshot["voltage_v"], snapshot["current_a"], snapshot["energy_kwh"], snapshot["session_energy_kwh"], snapshot["temperature_c"], snapshot["fault_code"], snapshot["alarm_code"], snapshot["source"], snapshot["recorded_at"]))
        return int(cursor.lastrowid)

    def latest_snapshot(self, charger_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM charger_snapshots WHERE charger_id = ? ORDER BY recorded_at DESC LIMIT 1", (charger_id,)).fetchone()
        if row is None:
            return None
        return {key: row[key] for key in row.keys() if key != "id" and key != "charger_id"}

    def list_snapshots(self, charger_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM charger_snapshots WHERE charger_id = ? ORDER BY recorded_at DESC LIMIT ?", (charger_id, limit)).fetchall()
        return [{key: row[key] for key in row.keys() if key not in {"id", "charger_id"}} for row in rows]

    def list_alarms(self, plan_id: str, active_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT alarms.*, devices.plan_id FROM alarms JOIN devices ON devices.id = alarms.charger_id WHERE devices.plan_id = ?"
        params: list[Any] = [plan_id]
        if active_only:
            query += " AND alarms.active = 1"
        query += " ORDER BY alarms.created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [{key: row[key] for key in row.keys() if key != "plan_id"} for row in rows]

    def save_alarm(self, alarm: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute("INSERT OR REPLACE INTO alarms (id, charger_id, code, severity, title, detail, active, created_at, cleared_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (alarm["id"], alarm["charger_id"], alarm["code"], alarm["severity"], alarm["title"], alarm["detail"], int(alarm["active"]), alarm["created_at"], alarm.get("cleared_at")))

    def list_sessions(self, plan_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT charging_sessions.*, devices.plan_id FROM charging_sessions JOIN devices ON devices.id = charging_sessions.charger_id WHERE devices.plan_id = ? ORDER BY started_at DESC", (plan_id,)).fetchall()
        return [{key: row[key] for key in row.keys() if key != "plan_id"} for row in rows]
