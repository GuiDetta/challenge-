from __future__ import annotations

import json
import sqlite3
from hashlib import pbkdf2_hmac
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class InsufficientBalanceError(ValueError):
    pass


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

    @staticmethod
    def generate_device_code() -> str:
        from uuid import uuid4

        return f"HC2-{uuid4().hex[:6].upper()}"

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
                    kind TEXT NOT NULL DEFAULT 'simulated',
                    code TEXT,
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
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('lojista', 'cliente', 'instalador')),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS charging_orders (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id),
                    charger_code TEXT NOT NULL,
                    energy_kwh REAL NOT NULL,
                    price_per_kwh REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    estimated_duration_minutes INTEGER NOT NULL,
                    payment_method TEXT NOT NULL CHECK (payment_method IN ('pix', 'paypal', 'wallet')),
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS wallet_transactions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id),
                    amount REAL NOT NULL,
                    type TEXT NOT NULL CHECK (type IN ('top_up', 'debit')),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS error_events (
                    id TEXT PRIMARY KEY,
                    reference TEXT NOT NULL,
                    code TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    owner_id TEXT,
                    detail TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_error_events_time ON error_events(occurred_at);
                CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
                CREATE INDEX IF NOT EXISTS idx_orders_user ON charging_orders(user_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_wallet_user ON wallet_transactions(user_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_rooms_plan ON rooms(plan_id);
                CREATE INDEX IF NOT EXISTS idx_devices_plan ON devices(plan_id);
                CREATE INDEX IF NOT EXISTS idx_snapshots_charger_time ON charger_snapshots(charger_id, recorded_at);
                CREATE INDEX IF NOT EXISTS idx_alarms_charger_active ON alarms(charger_id, active);
                """
            )
            self.ensure_device_kind_column()
            self.ensure_device_code_column()
            self.ensure_device_owner_column()
            self.ensure_device_active_column()
            self.ensure_plan_owner_column()

    def ensure_device_kind_column(self) -> None:
        with self.connect() as connection:
            columns = connection.execute("PRAGMA table_info(devices)").fetchall()
            if not any(column[1] == "kind" for column in columns):
                connection.execute("ALTER TABLE devices ADD COLUMN kind TEXT NOT NULL DEFAULT 'simulated'")

    def ensure_device_code_column(self) -> None:
        with self.connect() as connection:
            columns = connection.execute("PRAGMA table_info(devices)").fetchall()
            if not any(column[1] == "code" for column in columns):
                connection.execute("ALTER TABLE devices ADD COLUMN code TEXT")
            rows = connection.execute("SELECT id FROM devices WHERE code IS NULL OR code = ''").fetchall()
            for row in rows:
                connection.execute("UPDATE devices SET code = ? WHERE id = ?", (self.generate_device_code(), row["id"]))

    def ensure_device_owner_column(self) -> None:
        with self.connect() as connection:
            columns = connection.execute("PRAGMA table_info(devices)").fetchall()
            if not any(column[1] == "owner_id" for column in columns):
                connection.execute("ALTER TABLE devices ADD COLUMN owner_id TEXT")

    def ensure_device_active_column(self) -> None:
        with self.connect() as connection:
            columns = connection.execute("PRAGMA table_info(devices)").fetchall()
            if not any(column[1] == "active" for column in columns):
                connection.execute("ALTER TABLE devices ADD COLUMN active INTEGER NOT NULL DEFAULT 1")

    def ensure_plan_owner_column(self) -> None:
        with self.connect() as connection:
            columns = connection.execute("PRAGMA table_info(plans)").fetchall()
            if not any(column[1] == "owner_id" for column in columns):
                connection.execute("ALTER TABLE plans ADD COLUMN owner_id TEXT")
            connection.execute(
                """
                UPDATE plans
                SET owner_id = (
                    SELECT MIN(d.owner_id)
                    FROM devices d
                    WHERE d.plan_id = plans.id AND d.owner_id IS NOT NULL
                )
                WHERE owner_id IS NULL
                  AND (SELECT COUNT(DISTINCT d.owner_id) FROM devices d WHERE d.plan_id = plans.id AND d.owner_id IS NOT NULL) = 1
                """
            )

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def save_plan(self, plan: dict[str, Any], original_filename: str, owner_id: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute("INSERT OR REPLACE INTO plans (id, owner_id, width, height, svg, original_filename, ocr_available, warnings_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (plan["plan_id"], owner_id, plan["width"], plan["height"], plan["svg"], original_filename, int(plan["ocr_available"]), json.dumps(plan.get("warnings", []), ensure_ascii=False), self.now()))
            connection.execute("DELETE FROM rooms WHERE plan_id = ?", (plan["plan_id"],))
            connection.executemany("INSERT INTO rooms (id, plan_id, name, polygon_json, bounds_json, area) VALUES (?, ?, ?, ?, ?, ?)", [(room["id"], plan["plan_id"], room["name"], json.dumps(room["polygon"]), json.dumps(room["bounds"]), room["area"]) for room in plan["rooms"]])

    def get_plan(self, plan_id: str, owner_id: str | None = None) -> dict[str, Any] | None:
        with self.connect() as connection:
            query = "SELECT * FROM plans WHERE id = ?"
            params: list[Any] = [plan_id]
            if owner_id:
                query += " AND owner_id = ?"
                params.append(owner_id)
            row = connection.execute(query, params).fetchone()
            if row is None:
                return None
            rooms = connection.execute("SELECT * FROM rooms WHERE plan_id = ? ORDER BY id", (plan_id,)).fetchall()
        return {"plan_id": row["id"], "owner_id": row["owner_id"], "width": row["width"], "height": row["height"], "svg": row["svg"], "rooms": [{"id": room["id"], "name": room["name"], "polygon": json.loads(room["polygon_json"]), "bounds": json.loads(room["bounds_json"]), "area": room["area"]} for room in rooms], "walls": [], "texts": [], "ocr_available": bool(row["ocr_available"]), "warnings": json.loads(row["warnings_json"])}

    def list_plans_for_owner(self, owner_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT p.id FROM plans p WHERE p.owner_id = ? ORDER BY p.created_at",
                (owner_id,),
            ).fetchall()
        return [plan for row in rows if (plan := self.get_plan(row["id"])) is not None]

    def add_device(self, plan_id: str, device: dict[str, Any]) -> None:
        metadata = dict(device.get("metadata", {}))
        kind = device.get("kind") or metadata.get("kind") or "simulated"
        code = device.get("code") or metadata.get("code") or self.generate_device_code()
        metadata["kind"] = kind
        metadata["code"] = code
        with self.connect() as connection:
            connection.execute("INSERT INTO devices (id, plan_id, room_id, name, device_type, model, power_kw, phase, rated_current_a, kind, code, owner_id, x, y, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (device["id"], plan_id, device.get("room_id"), device["name"], device["device_type"], device.get("model"), device.get("power_kw"), device.get("phase"), device.get("rated_current_a"), kind, code, device.get("owner_id"), device["x"], device["y"], json.dumps(metadata, ensure_ascii=False), self.now()))

    def update_device(self, device_id: str, updates: dict[str, Any]) -> bool:
        if not updates:
            return True
        assignments = []
        params: list[Any] = []
        for key, value in updates.items():
            assignments.append(f"{key} = ?")
            params.append(value)
        params.append(device_id)
        with self.connect() as connection:
            cursor = connection.execute(f"UPDATE devices SET {', '.join(assignments)} WHERE id = ?", params)
        return cursor.rowcount > 0

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        return self._device(row) if row else None

    def list_devices(self, plan_id: str, device_type: str | None = None, owner_id: str | None = None, include_inactive: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM devices WHERE plan_id = ?"
        params: list[Any] = [plan_id]
        if not include_inactive:
            query += " AND active = 1"
        if device_type:
            query += " AND device_type = ?"
            params.append(device_type)
        if owner_id:
            query += " AND owner_id = ?"
            params.append(owner_id)
        with self.connect() as connection:
            rows = connection.execute(query + " ORDER BY name", params).fetchall()
        return [self._device(row) for row in rows]

    def list_real_chargers(self, owner_id: str, include_inactive: bool = False) -> list[dict[str, Any]]:
        active_filter = "" if include_inactive else " AND active = 1"
        with self.connect() as connection:
            rows = connection.execute(f"SELECT * FROM devices WHERE device_type = ? AND kind = ? AND owner_id = ?{active_filter} ORDER BY name", ("charger", "real", owner_id)).fetchall()
        return [self._device(row) for row in rows]

    def deactivate_device(self, device_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("UPDATE devices SET active = 0 WHERE id = ?", (device_id,))
        return cursor.rowcount > 0

    def delete_device(self, device_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        return cursor.rowcount > 0

    @staticmethod
    def hash_password(password: str) -> str:
        return pbkdf2_hmac("sha256", password.encode(), b"goodwe-salt-v1", 120_000).hex()

    def create_user(self, user: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute("INSERT INTO users (id, name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)", (user["id"], user["name"], user["email"].lower(), self.hash_password(user["password"]), user["role"], self.now()))
        return self.get_user(user["id"])

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT id, name, email, role, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def authenticate_user(self, email: str, password: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        if not row or row["password_hash"] != self.hash_password(password):
            return None
        user = {key: row[key] for key in ("id", "name", "email", "role", "created_at")}
        with self.connect() as connection:
            balance = connection.execute("SELECT COALESCE(SUM(CASE WHEN type = 'top_up' THEN amount ELSE -amount END), 0) FROM wallet_transactions WHERE user_id = ?", (row["id"],)).fetchone()[0]
        user["wallet_balance"] = round(float(balance), 2)
        return user

    def get_charger_by_code(self, code: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM devices WHERE code = ? AND device_type = 'charger' AND kind = 'real'", (code,)).fetchone()
        return self._device(row) if row else None

    def activate_charger_by_code(self, code: str) -> bool:
        charger = self.get_charger_by_code(code)
        if charger is None:
            return False
        metadata = {**(charger.get("metadata") or {}), "payment_active": "true"}
        with self.connect() as connection:
            cursor = connection.execute("UPDATE devices SET metadata_json = ? WHERE id = ?", (json.dumps(metadata, ensure_ascii=False), charger["id"]))
        return cursor.rowcount > 0

    def create_order(self, order: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as connection:
            balance = connection.execute(
                "SELECT COALESCE(SUM(CASE WHEN type = 'top_up' THEN amount ELSE -amount END), 0) FROM wallet_transactions WHERE user_id = ?",
                (order["user_id"],),
            ).fetchone()[0]
            if float(balance) < float(order["total_amount"]):
                raise InsufficientBalanceError
            connection.execute(
                "INSERT INTO wallet_transactions (id, user_id, amount, type, created_at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid4()), order["user_id"], order["total_amount"], "debit", self.now()),
            )
            connection.execute("INSERT INTO charging_orders (id, user_id, charger_code, energy_kwh, price_per_kwh, total_amount, scheduled_at, estimated_duration_minutes, payment_method, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (order["id"], order["user_id"], order["charger_code"], order["energy_kwh"], order["price_per_kwh"], order["total_amount"], order["scheduled_at"], order["estimated_duration_minutes"], order["payment_method"], "active", self.now()))
        return self.get_order(order["id"])

    def complete_due_orders(self) -> None:
        now = datetime.now(timezone.utc)
        with self.connect() as connection:
            rows = connection.execute("SELECT id, charger_code, created_at, estimated_duration_minutes FROM charging_orders WHERE status = 'active'").fetchall()
            for row in rows:
                started_at = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                if now < started_at + timedelta(minutes=row["estimated_duration_minutes"]):
                    continue
                connection.execute("UPDATE charging_orders SET status = 'completed' WHERE id = ?", (row["id"],))
                charger = connection.execute("SELECT id, metadata_json FROM devices WHERE code = ?", (row["charger_code"],)).fetchone()
                if charger:
                    metadata = json.loads(charger["metadata_json"] or "{}")
                    metadata["payment_active"] = "false"
                    connection.execute("UPDATE devices SET metadata_json = ? WHERE id = ?", (json.dumps(metadata, ensure_ascii=False), charger["id"]))

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM charging_orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row) if row else None

    def get_active_order_for_charger(self, charger_code: str, user_id: str | None = None) -> dict[str, Any] | None:
        with self.connect() as connection:
            query = "SELECT * FROM charging_orders WHERE charger_code = ? AND status = 'active'"
            params: list[Any] = [charger_code]
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            query += " ORDER BY created_at DESC LIMIT 1"
            row = connection.execute(query, params).fetchone()
        return dict(row) if row else None

    def finish_order(self, order_id: str, user_id: str, energy_delivered_kwh: float) -> dict[str, Any]:
        with self.connect() as connection:
            order = connection.execute(
                "SELECT * FROM charging_orders WHERE id = ? AND user_id = ? AND status = 'active'",
                (order_id, user_id),
            ).fetchone()
            if order is None:
                raise ValueError("Pedido ativo não encontrado.")
            delivered = min(float(energy_delivered_kwh), float(order["energy_kwh"]))
            charged_amount = round(delivered * float(order["price_per_kwh"]), 2)
            refund_amount = max(0, round(float(order["total_amount"]) - charged_amount, 2))
            connection.execute(
                "UPDATE charging_orders SET status = 'completed', energy_kwh = ? WHERE id = ?",
                (delivered, order_id),
            )
            charger = connection.execute(
                "SELECT id, metadata_json FROM devices WHERE code = ?",
                (order["charger_code"],),
            ).fetchone()
            if charger:
                metadata = json.loads(charger["metadata_json"] or "{}")
                metadata["payment_active"] = "false"
                connection.execute(
                    "UPDATE devices SET metadata_json = ? WHERE id = ?",
                    (json.dumps(metadata, ensure_ascii=False), charger["id"]),
                )
            if refund_amount > 0:
                connection.execute(
                    "INSERT INTO wallet_transactions (id, user_id, amount, type, created_at) VALUES (?, ?, ?, 'top_up', ?)",
                    (str(uuid4()), user_id, refund_amount, self.now()),
                )
            balance = connection.execute(
                "SELECT COALESCE(SUM(CASE WHEN type = 'top_up' THEN amount ELSE -amount END), 0) FROM wallet_transactions WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
        return {"order_id": order_id, "energy_delivered_kwh": delivered, "refund_amount": refund_amount, "wallet_balance": round(float(balance), 2)}

    def add_wallet_transaction(self, transaction: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute("INSERT INTO wallet_transactions (id, user_id, amount, type, created_at) VALUES (?, ?, ?, ?, ?)", (transaction["id"], transaction["user_id"], transaction["amount"], transaction["type"], self.now()))
        return transaction

    def report_summary(self, owner_id: str | None = None) -> dict[str, Any]:
        self.complete_due_orders()
        local_now = datetime.now().astimezone()
        month_prefix = local_now.strftime("%Y-%m")
        with self.connect() as connection:
            scope = " AND owner_id = ?" if owner_id else ""
            params = (owner_id,) if owner_id else ()
            charger_count = connection.execute(f"SELECT COUNT(*) FROM devices WHERE device_type = 'charger' AND kind = 'real' AND active = 1{scope}", params).fetchone()[0]
            completed_rows = connection.execute(f"SELECT o.created_at, o.energy_kwh, o.total_amount, d.owner_id FROM charging_orders o JOIN devices d ON d.code = o.charger_code WHERE o.status = 'completed'{scope.replace('owner_id', 'd.owner_id')}", params).fetchall()
            completed = [row for row in completed_rows if not owner_id or row["owner_id"] == owner_id]
            revenue = sum(float(row["total_amount"]) for row in completed)
            month_rows = [row for row in completed if datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")).astimezone().strftime("%Y-%m") == month_prefix]
            month_revenue = sum(float(row["total_amount"]) for row in month_rows)
            month_energy = sum(float(row["energy_kwh"]) for row in month_rows)
            charger_rows = connection.execute(f"SELECT d.name, d.code, d.power_kw, COALESCE((SELECT SUM(o.energy_kwh) FROM charging_orders o WHERE o.charger_code = d.code AND o.status = 'completed'), 0) AS energy_kwh FROM devices d WHERE d.device_type = 'charger' AND d.kind = 'real' AND d.active = 1{scope} ORDER BY d.name", params).fetchall()
        daily = {}
        for row in completed:
            day = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")).astimezone().date()
            if day >= local_now.date() - timedelta(days=6):
                item = daily.setdefault(day.isoformat(), {"energy_kwh": 0, "revenue": 0})
                item["energy_kwh"] += float(row["energy_kwh"])
                item["revenue"] += float(row["total_amount"])
        days = []
        for offset in range(6, -1, -1):
            day = local_now.date().fromordinal(local_now.date().toordinal() - offset).isoformat()
            days.append({"day": day, **daily.get(day, {"energy_kwh": 0, "revenue": 0})})
        chargers = [dict(row) for row in charger_rows]
        return {"charger_count": charger_count, "revenue_total": round(float(revenue), 2), "month_revenue": round(float(month_revenue), 2), "month_energy_kwh": round(float(month_energy), 2), "generated_energy_kwh": round(sum(float(item["energy_kwh"]) for item in chargers), 2), "chargers": chargers, "daily": days}

    def assistant_orders(self, owner_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT o.charger_code, o.energy_kwh, o.total_amount, o.payment_method, o.status, o.created_at FROM charging_orders o JOIN devices d ON d.code = o.charger_code WHERE d.owner_id = ? ORDER BY o.created_at DESC LIMIT 50",
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_error_event(self, event: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO error_events (id, reference, code, status_code, method, path, owner_id, detail, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (event["id"], event["reference"], event["code"], event["status_code"], event["method"], event["path"], event.get("owner_id"), event["detail"], event["occurred_at"]),
            )
        return event

    def list_error_events(self, owner_id: str | None, since: str, limit: int = 200) -> list[dict[str, Any]]:
        query = "SELECT * FROM error_events WHERE occurred_at >= ?"
        params: list[Any] = [since]
        if owner_id:
            query += " AND owner_id = ?"
            params.append(owner_id)
        query += " ORDER BY occurred_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def availability_rows(self, owner_id: str, since: str) -> list[dict[str, Any]]:
        """Uma amostra por carregador por minuto, para o tempo de leitura da tela não pesar na conta."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT d.id AS charger_id, d.name, d.code, s.status, COUNT(*) AS samples
                FROM (
                    SELECT MIN(id) AS id
                    FROM charger_snapshots
                    WHERE recorded_at >= ?
                    GROUP BY charger_id, substr(recorded_at, 1, 16)
                ) minute_sample
                JOIN charger_snapshots s ON s.id = minute_sample.id
                JOIN devices d ON d.id = s.charger_id
                WHERE d.owner_id = ? AND d.device_type = 'charger' AND d.active = 1
                GROUP BY d.id, s.status
                ORDER BY d.name
                """,
                (since, owner_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def fault_rows(self, owner_id: str, since: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            occurrences = connection.execute(
                """
                SELECT code, COUNT(*) AS occurrences, COUNT(DISTINCT charger_id) AS chargers, MAX(minute) AS last_seen
                FROM (
                    SELECT DISTINCT s.fault_code AS code, s.charger_id, substr(s.recorded_at, 1, 16) AS minute
                    FROM charger_snapshots s
                    JOIN devices d ON d.id = s.charger_id
                    WHERE d.owner_id = ? AND s.fault_code != 0 AND s.recorded_at >= ?
                )
                GROUP BY code
                ORDER BY occurrences DESC
                """,
                (owner_id, since),
            ).fetchall()
            active = connection.execute(
                "SELECT a.code, COUNT(*) AS active_alarms FROM alarms a JOIN devices d ON d.id = a.charger_id WHERE d.owner_id = ? AND a.active = 1 GROUP BY a.code",
                (owner_id,),
            ).fetchall()
        active_by_code = {row["code"]: row["active_alarms"] for row in active}
        return [{**dict(row), "active_alarms": active_by_code.get(row["code"], 0)} for row in occurrences]

    def demand_rows(self, owner_id: str, since: str) -> list[dict[str, Any]]:
        """Potência simultânea por minuto: média por carregador no minuto, somada entre carregadores."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT minute, SUM(power_kw) AS power_kw
                FROM (
                    SELECT substr(s.recorded_at, 1, 16) AS minute, s.charger_id, AVG(s.power_kw) AS power_kw
                    FROM charger_snapshots s
                    JOIN devices d ON d.id = s.charger_id
                    WHERE d.owner_id = ? AND s.recorded_at >= ?
                    GROUP BY minute, s.charger_id
                )
                GROUP BY minute
                ORDER BY minute
                """,
                (owner_id, since),
            ).fetchall()
        return [dict(row) for row in rows]

    def installed_power_kw(self, owner_id: str) -> float:
        with self.connect() as connection:
            total = connection.execute(
                "SELECT COALESCE(SUM(power_kw), 0) FROM devices WHERE owner_id = ? AND device_type = 'charger' AND active = 1",
                (owner_id,),
            ).fetchone()[0]
        return round(float(total), 2)

    def order_rows(self, owner_id: str, since: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT o.id, o.created_at, o.charger_code, o.energy_kwh, o.total_amount, o.status, o.payment_method, o.price_per_kwh, o.estimated_duration_minutes, d.name AS charger_name FROM charging_orders o JOIN devices d ON d.code = o.charger_code WHERE d.owner_id = ? AND o.created_at >= ? ORDER BY o.created_at",
                (owner_id, since),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _device(row: sqlite3.Row) -> dict[str, Any]:
        metadata = json.loads(row["metadata_json"] or "{}")
        kind = row["kind"] if "kind" in row.keys() else metadata.get("kind", "simulated")
        code = row["code"] if "code" in row.keys() and row["code"] else metadata.get("code")
        return {"id": row["id"], "plan_id": row["plan_id"], "room_id": row["room_id"], "name": row["name"], "device_type": row["device_type"], "model": row["model"], "power_kw": row["power_kw"], "phase": row["phase"], "rated_current_a": row["rated_current_a"], "kind": kind, "code": code, "owner_id": row["owner_id"] if "owner_id" in row.keys() else None, "active": bool(row["active"]) if "active" in row.keys() else True, "x": row["x"], "y": row["y"], "metadata": metadata}

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
