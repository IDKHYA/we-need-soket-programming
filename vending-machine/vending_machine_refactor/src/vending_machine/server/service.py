from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from vending_machine.network.schemas import EventBatchAck, MachineEventEnvelope
from vending_machine.server.db import Base, build_session_factory, session_scope
from vending_machine.server.models import (
    AdminAction,
    Alert,
    CashEvent,
    Machine,
    MachineCashStatus,
    MachineEvent,
    MachineProduct,
    MachineStatus,
    Product,
    SalesEvent,
    ServerHealthLog,
    ServerSyncLog,
    StockEvent,
)


@dataclass(frozen=True)
class ServerSettings:
    server_id: str
    database_url: str
    peer_server_id: str = "server2"
    peer_sync_host: str = "127.0.0.1"
    peer_sync_port: int = 9102
    low_stock_threshold: int = 2


class ServerIntegrationService:
    def __init__(self, settings: ServerSettings):
        self.settings = settings
        self.engine, self.session_factory = build_session_factory(settings.database_url)
        Base.metadata.create_all(self.engine)

    def apply_events(self, events: list[MachineEventEnvelope], trigger_sync: bool = True) -> EventBatchAck:
        accepted: list[str] = []
        duplicated: list[str] = []
        failed: list[str] = []
        with session_scope(self.session_factory) as session:
            for event in events:
                existing = session.get(MachineEvent, event.event_id)
                if existing:
                    duplicated.append(event.event_id)
                    continue
                self._apply_single_event(session, event)
                accepted.append(event.event_id)
        return EventBatchAck(
            accepted_event_ids=accepted,
            duplicated_event_ids=duplicated,
            failed_event_ids=failed,
            sync_triggered=trigger_sync and any(event.source == "machine" for event in events),
        )

    def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with session_scope(self.session_factory) as session:
            stmt = (
                select(MachineEvent)
                .order_by(MachineEvent.occurred_at.desc(), MachineEvent.sequence_no.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "event_id": row.event_id,
                    "machine_id": row.machine_id,
                    "server_id": row.server_id,
                    "event_type": row.event_type,
                    "source": row.source,
                    "occurred_at": row.occurred_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "payload": row.payload,
                }
                for row in rows
            ]

    def machine_statuses(self) -> list[dict[str, Any]]:
        with session_scope(self.session_factory) as session:
            stmt = (
                select(Machine, MachineStatus)
                .join(MachineStatus, MachineStatus.machine_id == Machine.machine_id)
                .order_by(Machine.machine_id)
            )
            rows = session.execute(stmt).all()
            return [
                {
                    "machine_id": machine.machine_id,
                    "server_id": machine.server_id,
                    "last_seen_at": _fmt_dt(machine.last_seen_at),
                    "current_balance": status.current_balance,
                    "total_cash_amount": status.total_cash_amount,
                    "last_event_id": status.last_event_id,
                    "last_event_type": status.last_event_type,
                    "last_event_at": _fmt_dt(status.last_event_at),
                }
                for machine, status in rows
            ]

    def active_alerts(self) -> list[dict[str, Any]]:
        with session_scope(self.session_factory) as session:
            stmt = select(Alert).where(Alert.active.is_(True)).order_by(Alert.machine_id, Alert.product_id)
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "machine_id": row.machine_id,
                    "product_id": row.product_id,
                    "product_name": row.product_name,
                    "alert_type": row.alert_type,
                    "current_stock": row.current_stock,
                    "threshold": row.threshold,
                    "raised_at": _fmt_dt(row.raised_at),
                }
                for row in rows
            ]

    def machine_sales_stats(self) -> list[dict[str, Any]]:
        with session_scope(self.session_factory) as session:
            stmt = (
                select(
                    SalesEvent.machine_id,
                    func.count(SalesEvent.event_id),
                    func.coalesce(func.sum(SalesEvent.qty), 0),
                    func.coalesce(func.sum(SalesEvent.paid_amount - SalesEvent.change_amount), 0),
                )
                .group_by(SalesEvent.machine_id)
                .order_by(SalesEvent.machine_id)
            )
            return [
                {
                    "machine_id": machine_id,
                    "sales_count": sales_count,
                    "units_sold": units_sold,
                    "net_sales": net_sales,
                }
                for machine_id, sales_count, units_sold, net_sales in session.execute(stmt).all()
            ]

    def product_sales_stats(self) -> list[dict[str, Any]]:
        with session_scope(self.session_factory) as session:
            stmt = (
                select(
                    SalesEvent.product_id,
                    SalesEvent.product_name,
                    func.coalesce(func.sum(SalesEvent.qty), 0),
                    func.coalesce(func.sum(SalesEvent.paid_amount - SalesEvent.change_amount), 0),
                )
                .group_by(SalesEvent.product_id, SalesEvent.product_name)
                .order_by(SalesEvent.product_id)
            )
            return [
                {
                    "product_id": product_id,
                    "product_name": product_name,
                    "units_sold": units_sold,
                    "net_sales": net_sales,
                }
                for product_id, product_name, units_sold, net_sales in session.execute(stmt).all()
            ]

    def sync_status(self) -> list[dict[str, Any]]:
        with session_scope(self.session_factory) as session:
            stmt = select(ServerSyncLog).order_by(ServerSyncLog.synced_at.desc()).limit(100)
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "event_id": row.event_id,
                    "source_server": row.source_server,
                    "target_server": row.target_server,
                    "status": row.status,
                    "message": row.message,
                    "synced_at": _fmt_dt(row.synced_at),
                }
                for row in rows
            ]

    def record_sync_result(self, event_id: str, target_server: str, status: str, message: str = "") -> None:
        with session_scope(self.session_factory) as session:
            session.add(
                ServerSyncLog(
                    event_id=event_id,
                    source_server=self.settings.server_id,
                    target_server=target_server,
                    status=status,
                    message=message,
                )
            )

    def record_health(self, status: str, detail: str = "") -> None:
        with session_scope(self.session_factory) as session:
            session.add(ServerHealthLog(server_id=self.settings.server_id, status=status, detail=detail))

    def _apply_single_event(self, session, event: MachineEventEnvelope) -> None:
        occurred_at = _parse_dt(event.occurred_at)
        machine = session.get(Machine, event.machine_id)
        if machine is None:
            machine = Machine(machine_id=event.machine_id, server_id=event.server_id)
            session.add(machine)
        machine.server_id = event.server_id
        machine.last_seen_at = occurred_at

        status = session.get(MachineStatus, event.machine_id)
        if status is None:
            status = MachineStatus(machine_id=event.machine_id, server_id=event.server_id)
            session.add(status)

        session.add(
            MachineEvent(
                event_id=event.event_id,
                machine_id=event.machine_id,
                server_id=event.server_id,
                event_type=event.event_type,
                source=event.source,
                occurred_at=occurred_at,
                sequence_no=event.sequence_no,
                sheet_name=event.sheet_name,
                payload=event.payload,
                synced_to_peer=event.source == "server_sync",
            )
        )

        status.server_id = event.server_id
        status.last_event_id = event.event_id
        status.last_event_type = event.event_type
        status.last_event_at = occurred_at
        status.updated_at = datetime.utcnow()
        status.current_balance = _current_balance_from_payload(event.payload, status.current_balance)
        status.total_cash_amount = _next_cash_total(event, status.total_cash_amount)

        if event.sheet_name == "sales_log":
            self._apply_sale(session, event, occurred_at)
        elif event.sheet_name == "stock_log":
            self._apply_stock(session, event, occurred_at)
        elif event.sheet_name == "cash_log":
            self._apply_cash(session, event, occurred_at)
        elif event.sheet_name == "audit_log":
            self._apply_admin(session, event, occurred_at)

    def _apply_sale(self, session, event: MachineEventEnvelope, occurred_at: datetime) -> None:
        payload = event.payload
        session.add(
            SalesEvent(
                event_id=event.event_id,
                machine_id=event.machine_id,
                product_id=str(payload.get("product_id", "")),
                product_name=str(payload.get("product_name", "")),
                unit_price=int(payload.get("unit_price", 0)),
                qty=int(payload.get("qty", 0)),
                paid_amount=int(payload.get("paid_amount", 0)),
                change_amount=int(payload.get("change_amount", 0)),
                occurred_at=occurred_at,
            )
        )
        self._ensure_machine_product(
            session=session,
            machine_id=event.machine_id,
            product_id=str(payload.get("product_id", "")),
            product_name=str(payload.get("product_name", "")),
            price=int(payload.get("unit_price", 0)),
        )

    def _apply_stock(self, session, event: MachineEventEnvelope, occurred_at: datetime) -> None:
        payload = event.payload
        product_id = str(payload.get("product_id", ""))
        product_name = str(payload.get("product_name", ""))
        after_stock = int(payload.get("after_stock", 0))
        session.add(
            StockEvent(
                event_id=event.event_id,
                machine_id=event.machine_id,
                product_id=product_id,
                product_name=product_name,
                action=str(payload.get("event_type", "")),
                before_stock=int(payload.get("before_stock", 0)),
                change_qty=int(payload.get("change_qty", 0)),
                after_stock=after_stock,
                occurred_at=occurred_at,
            )
        )
        item = self._ensure_machine_product(session, event.machine_id, product_id, product_name)
        item.stock = after_stock
        item.updated_at = datetime.utcnow()
        self._evaluate_alert(session, item)

    def _apply_cash(self, session, event: MachineEventEnvelope, occurred_at: datetime) -> None:
        payload = event.payload
        action = str(payload.get("event_type", "CASH"))
        denomination = int(payload.get("denomination", 0))
        qty = int(payload.get("qty", 0))
        amount = int(payload.get("amount", 0))
        session.add(
            CashEvent(
                event_id=event.event_id,
                machine_id=event.machine_id,
                action=action,
                denomination=denomination,
                qty=qty,
                amount=amount,
                occurred_at=occurred_at,
            )
        )
        self._update_cash_status(session, event.machine_id, action, denomination, qty)

    def _apply_admin(self, session, event: MachineEventEnvelope, occurred_at: datetime) -> None:
        payload = event.payload
        session.add(
            AdminAction(
                event_id=event.event_id,
                machine_id=event.machine_id,
                actor=str(payload.get("actor", "admin")),
                action=str(payload.get("action", "AUDIT")),
                target=str(payload.get("target", "")),
                detail=str(payload.get("detail", "")),
                occurred_at=occurred_at,
            )
        )
        changes = payload.get("changes")
        if isinstance(changes, dict):
            product_id = str(payload.get("target", ""))
            item = self._ensure_machine_product(
                session,
                event.machine_id,
                product_id,
                str(changes.get("name", ["", ""])[1] if "name" in changes else product_id),
            )
            if "name" in changes:
                item.product_name = str(changes["name"][1])
            if "price" in changes:
                item.price = int(changes["price"][1])
            if "max_stock" in changes:
                item.max_stock = int(changes["max_stock"][1])
            if "active" in changes:
                item.active = bool(changes["active"][1])
            item.updated_at = datetime.utcnow()

    def _ensure_machine_product(
        self,
        session,
        machine_id: str,
        product_id: str,
        product_name: str,
        price: int = 0,
    ) -> MachineProduct:
        product = session.get(Product, product_id)
        if product is None:
            product = Product(product_id=product_id, name=product_name or product_id)
            session.add(product)
        else:
            product.name = product_name or product.name

        stmt = select(MachineProduct).where(
            MachineProduct.machine_id == machine_id,
            MachineProduct.product_id == product_id,
        )
        item = session.execute(stmt).scalar_one_or_none()
        if item is None:
            item = MachineProduct(
                machine_id=machine_id,
                product_id=product_id,
                product_name=product_name or product_id,
                price=price,
                stock=0,
                max_stock=0,
                low_stock_threshold=self.settings.low_stock_threshold,
            )
            session.add(item)
        if product_name:
            item.product_name = product_name
        if price:
            item.price = price
        return item

    def _update_cash_status(self, session, machine_id: str, action: str, denomination: int, qty: int) -> None:
        stmt = select(MachineCashStatus).where(
            MachineCashStatus.machine_id == machine_id,
            MachineCashStatus.denomination == denomination,
        )
        row = session.execute(stmt).scalar_one_or_none()
        if row is None:
            row = MachineCashStatus(machine_id=machine_id, denomination=denomination, quantity=0)
            session.add(row)
        if action in {"INSERT", "REFILL_CASH"}:
            row.quantity += qty
        elif action in {"REFUND", "COLLECT"}:
            row.quantity = max(0, row.quantity - qty)
        row.updated_at = datetime.utcnow()

    def _evaluate_alert(self, session, item: MachineProduct) -> None:
        stmt = select(Alert).where(
            Alert.machine_id == item.machine_id,
            Alert.product_id == item.product_id,
        )
        existing = {row.alert_type: row for row in session.execute(stmt).scalars().all()}
        now = datetime.utcnow()

        out_of_stock = item.stock == 0
        low_stock = 0 < item.stock <= item.low_stock_threshold

        self._upsert_alert(session, existing.get("OUT_OF_STOCK"), item, "OUT_OF_STOCK", out_of_stock, now)
        self._upsert_alert(session, existing.get("LOW_STOCK"), item, "LOW_STOCK", low_stock, now)

    def _upsert_alert(self, session, row, item: MachineProduct, alert_type: str, active: bool, now: datetime) -> None:
        if row is None and not active:
            return
        if row is None:
            row = Alert(
                machine_id=item.machine_id,
                product_id=item.product_id,
                product_name=item.product_name,
                alert_type=alert_type,
                current_stock=item.stock,
                threshold=item.low_stock_threshold,
                active=active,
                raised_at=now,
                resolved_at=None if active else now,
            )
            session.add(row)
            return
        row.product_name = item.product_name
        row.current_stock = item.stock
        row.threshold = item.low_stock_threshold
        row.active = active
        if active:
            if row.resolved_at is not None:
                row.raised_at = now
            row.resolved_at = None
        else:
            row.resolved_at = now


def _parse_dt(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"지원하지 않는 날짜 형식입니다: {value}")


def _fmt_dt(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def _current_balance_from_payload(payload: dict[str, Any], default: int | None) -> int:
    base = 0 if default is None else int(default)
    if "remaining_balance" in payload:
        return int(payload["remaining_balance"])
    if payload.get("event_type") == "INSERT":
        return base + int(payload.get("amount", 0))
    if payload.get("event_type") == "REFUND":
        return 0
    return base


def _next_cash_total(event: MachineEventEnvelope, current_total: int | None) -> int:
    base = 0 if current_total is None else int(current_total)
    if event.sheet_name != "cash_log":
        return base
    amount = int(event.payload.get("amount", 0))
    action = str(event.payload.get("event_type", ""))
    if action in {"INSERT", "REFILL_CASH"}:
        return base + amount
    if action in {"REFUND", "COLLECT"}:
        return max(0, base - amount)
    return base
