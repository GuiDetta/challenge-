from datetime import datetime, timedelta, timezone

from app.repositories import Database
from app.schemas import (
    AvailabilityReport,
    ChargerAvailability,
    DemandDay,
    DemandReport,
    FaultItem,
    FaultReport,
    OccupancyHour,
    OccupancyReport,
    OperationsReport,
)
from app.services import csv_export, fault_catalog

OPERATIONAL_STATUSES = {"available", "preparing", "charging", "suspended", "finished"}


def _percent(part: float, total: float) -> float:
    return round(part / total * 100, 1) if total else 0.0


def _to_local(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone()


class ReportService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def operations(self, owner_id: str, days: int = 7, contracted_kw: float | None = None) -> OperationsReport:
        self.database.complete_due_orders()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return OperationsReport(
            days=days,
            generated_at=datetime.now(timezone.utc).isoformat(),
            availability=self.availability(owner_id, since),
            faults=self.faults(owner_id, since),
            occupancy=self.occupancy(owner_id, since),
            demand=self.demand(owner_id, since, contracted_kw),
        )

    def availability(self, owner_id: str, since: str) -> AvailabilityReport:
        by_charger: dict[str, dict] = {}
        for row in self.database.availability_rows(owner_id, since):
            charger = by_charger.setdefault(
                row["charger_id"],
                {"name": row["name"], "code": row["code"], "total": 0, "up": 0, "charging": 0, "faulted": 0, "offline": 0},
            )
            samples = int(row["samples"])
            charger["total"] += samples
            if row["status"] in OPERATIONAL_STATUSES:
                charger["up"] += samples
            if row["status"] == "charging":
                charger["charging"] += samples
            if row["status"] == "faulted":
                charger["faulted"] += samples
            if row["status"] == "offline":
                charger["offline"] += samples

        chargers = [
            ChargerAvailability(
                charger_id=charger_id,
                name=data["name"],
                code=data["code"],
                samples=data["total"],
                uptime_percent=_percent(data["up"], data["total"]),
                charging_percent=_percent(data["charging"], data["total"]),
                fault_percent=_percent(data["faulted"], data["total"]),
                offline_percent=_percent(data["offline"], data["total"]),
            )
            for charger_id, data in by_charger.items()
        ]
        chargers.sort(key=lambda item: item.uptime_percent)
        total_samples = sum(item.samples for item in chargers)
        total_up = sum(data["up"] for data in by_charger.values())
        return AvailabilityReport(
            fleet_uptime_percent=_percent(total_up, total_samples),
            samples=total_samples,
            chargers=chargers,
        )

    def faults(self, owner_id: str, since: str) -> FaultReport:
        items = []
        for row in self.database.fault_rows(owner_id, since):
            described = fault_catalog.describe(int(row["code"]))
            items.append(
                FaultItem(
                    code=int(row["code"]),
                    title=described["title"],
                    severity=described["severity"],
                    origin=described["origin"],
                    first_action=described["first_action"],
                    escalation=described["escalation"],
                    occurrences=int(row["occurrences"]),
                    chargers=int(row["chargers"]),
                    active_alarms=int(row["active_alarms"]),
                    last_seen=_to_local(f"{row['last_seen']}:00+00:00").isoformat() if row["last_seen"] else None,
                )
            )
        return FaultReport(
            total_occurrences=sum(item.occurrences for item in items),
            active_alarms=sum(item.active_alarms for item in items),
            items=items,
        )

    def occupancy(self, owner_id: str, since: str) -> OccupancyReport:
        hours = {hour: {"sessions": 0, "energy_kwh": 0.0, "revenue": 0.0} for hour in range(24)}
        total_energy = 0.0
        total_revenue = 0.0
        orders = self.database.order_rows(owner_id, since)
        for order in orders:
            bucket = hours[_to_local(order["created_at"]).hour]
            bucket["sessions"] += 1
            bucket["energy_kwh"] += float(order["energy_kwh"])
            bucket["revenue"] += float(order["total_amount"])
            total_energy += float(order["energy_kwh"])
            total_revenue += float(order["total_amount"])

        peak_hour = max(hours, key=lambda hour: hours[hour]["sessions"]) if orders else None
        return OccupancyReport(
            total_sessions=len(orders),
            peak_hour=peak_hour,
            peak_sessions=hours[peak_hour]["sessions"] if peak_hour is not None else 0,
            average_energy_kwh=round(total_energy / len(orders), 2) if orders else 0.0,
            average_ticket=round(total_revenue / len(orders), 2) if orders else 0.0,
            hours=[
                OccupancyHour(
                    hour=hour,
                    sessions=data["sessions"],
                    energy_kwh=round(data["energy_kwh"], 2),
                    revenue=round(data["revenue"], 2),
                )
                for hour, data in hours.items()
            ],
        )

    def error_log(self, owner_id: str | None, days: int = 7, limit: int = 200) -> list[dict]:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        events = self.database.list_error_events(owner_id, since, limit)
        return [{**event, "occurred_at": _to_local(event["occurred_at"]).isoformat()} for event in events]

    def financial_csv(self, owner_id: str, days: int) -> str:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = []
        for order in self.database.order_rows(owner_id, since):
            moment = _to_local(order["created_at"])
            rows.append(
                [
                    moment.strftime("%d/%m/%Y"),
                    moment.strftime("%H:%M"),
                    order["charger_name"],
                    order["charger_code"],
                    csv_export.decimal(order["energy_kwh"]),
                    csv_export.decimal(order["price_per_kwh"]),
                    csv_export.decimal(order["total_amount"]),
                    order["payment_method"],
                    order["status"],
                    order["estimated_duration_minutes"],
                    order["id"],
                ]
            )
        return csv_export.build(
            ["Data", "Hora", "Carregador", "Código", "Energia (kWh)", "Preço por kWh (R$)", "Total (R$)", "Pagamento", "Situação", "Duração estimada (min)", "Pedido"],
            rows,
        )

    def availability_csv(self, owner_id: str, days: int) -> str:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        report = self.availability(owner_id, since)
        rows = [
            [
                charger.name,
                charger.code or "",
                charger.samples,
                csv_export.decimal(charger.uptime_percent, 1),
                csv_export.decimal(charger.charging_percent, 1),
                csv_export.decimal(charger.fault_percent, 1),
                csv_export.decimal(charger.offline_percent, 1),
            ]
            for charger in report.chargers
        ]
        return csv_export.build(
            ["Carregador", "Código", "Leituras", "Disponível (%)", "Carregando (%)", "Em falha (%)", "Offline (%)"],
            rows,
        )

    def faults_csv(self, owner_id: str, days: int) -> str:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        report = self.faults(owner_id, since)
        rows = [
            [
                item.code,
                item.title,
                item.severity,
                item.occurrences,
                item.chargers,
                item.active_alarms,
                (item.last_seen or "")[:16].replace("T", " "),
                item.origin,
                item.first_action,
                item.escalation,
            ]
            for item in report.items
        ]
        return csv_export.build(
            ["Código", "Falha", "Severidade", "Ocorrências", "Carregadores", "Alarmes ativos", "Última vez", "Origem provável", "Primeira ação", "Quando escalar"],
            rows,
        )

    def errors_csv(self, owner_id: str | None, days: int) -> str:
        rows = [
            [
                event["occurred_at"][:16].replace("T", " "),
                event["code"],
                event["reference"],
                event["status_code"],
                event["method"],
                event["path"],
                event["owner_id"] or "",
                event["detail"],
            ]
            for event in self.error_log(owner_id, days, limit=1000)
        ]
        return csv_export.build(
            ["Quando", "Código", "Referência", "HTTP", "Método", "Rota", "Usuário", "Detalhe"],
            rows,
        )

    def demand(self, owner_id: str, since: str, contracted_kw: float | None = None) -> DemandReport:
        installed_kw = self.database.installed_power_kw(owner_id)
        rows = self.database.demand_rows(owner_id, since)
        peak_kw = 0.0
        peak_at = None
        daily: dict[str, float] = {}
        for row in rows:
            power = round(float(row["power_kw"]), 2)
            recorded_at = _to_local(f"{row['minute']}:00+00:00")
            if power > peak_kw:
                peak_kw, peak_at = power, recorded_at.isoformat()
            day = recorded_at.date().isoformat()
            daily[day] = max(daily.get(day, 0.0), power)

        reference = contracted_kw or installed_kw
        headroom = round(100 - peak_kw / reference * 100, 1) if reference else None
        return DemandReport(
            installed_kw=installed_kw,
            contracted_kw=contracted_kw,
            peak_kw=peak_kw,
            peak_at=peak_at,
            headroom_percent=headroom,
            daily=[DemandDay(day=day, peak_kw=power) for day, power in sorted(daily.items())],
        )
